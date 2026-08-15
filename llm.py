# llm.py
"""Adaptateur LLM — résumé de transcript vidéo.

Priorité : BYOK par requête > clé d'instance OpenRouter > OpenCode Go > OpenAI-
compatible > repli honnête (erreur explicite, jamais de résumé inventé)."""
from __future__ import annotations

import ipaddress
import os
import socket
import time
from urllib.parse import urlparse

import httpx

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
OPENROUTER_BASE = "https://openrouter.ai/api/v1"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

OPENCODE_GO_API_KEY = os.getenv("OPENCODE_GO_API_KEY", "")
OPENCODE_GO_BASE_URL = os.getenv("OPENCODE_GO_BASE_URL", "https://opencode.ai/zen/go/v1")
OPENCODE_GO_MODEL = os.getenv("OPENCODE_GO_MODEL", "deepseek-v4-pro")


def config(llm: dict | None) -> tuple[str, str, str]:
    """(base_url, cle, modele) : BYO si fourni et complet, sinon OpenRouter en
    priorité, puis OpenCode Go, puis OpenAI comme fournisseurs par défaut de l'instance."""
    llm = llm or {}
    base = (llm.get("base_url") or "").strip()
    if base:
        return base.rstrip("/"), (llm.get("cle") or "").strip(), (llm.get("modele") or "").strip()
    modele = (llm.get("modele") or "").strip()
    if OPENROUTER_API_KEY:
        return OPENROUTER_BASE, OPENROUTER_API_KEY, modele or OPENROUTER_MODEL
    if OPENCODE_GO_API_KEY:
        return OPENCODE_GO_BASE_URL, OPENCODE_GO_API_KEY, modele or OPENCODE_GO_MODEL
    if OPENAI_API_KEY:
        return OPENAI_BASE_URL, OPENAI_API_KEY, modele or OPENAI_MODEL
    return "", "", ""


class ErreurLLM(Exception):
    """Erreur explicite remontée à l'appelant — jamais de contenu inventé en repli."""
    def __init__(self, message: str, code: int = 422):
        super().__init__(message)
        self.code = code


def _valider_base_url(base_url: str) -> None:
    """Empêche le SSRF le plus courant : refuse toute base_url qui résout vers une
    IP privée/interne au moment de la validation. Limite connue et acceptée pour
    l'instant : la résolution DNS n'est pas figée entre cette validation et l'appel
    HTTP réel — une attaque par DNS rebinding (TTL court, IP publique puis privée)
    n'est pas couverte."""
    parsed = urlparse(base_url)
    if parsed.scheme not in ("http", "https"):
        raise ErreurLLM("URL de fournisseur invalide (http/https uniquement).")
    host = parsed.hostname
    if not host:
        raise ErreurLLM("URL de fournisseur invalide.")
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as e:
        raise ErreurLLM(f"Impossible de résoudre l'hôte du fournisseur : {str(e)[:100]}")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise ErreurLLM("URL de fournisseur refusée (adresse privée/interne).")


def completer(prompt: str, llm: dict | None, max_tokens: int, temperature: float = 0.5) -> str:
    """Un appel chat-completion, avec un seul retry court sur 429."""
    base, cle, modele = config(llm)
    if not cle or not modele:
        raise ErreurLLM("Aucun modèle LLM configuré (ni BYOK, ni clé par défaut de l'instance).")
    _valider_base_url(base)
    headers = {"Authorization": f"Bearer {cle}"}
    payload = {"model": modele, "temperature": temperature, "max_tokens": max_tokens,
               "messages": [{"role": "user", "content": prompt}]}
    try:
        with httpx.Client(timeout=120) as c:
            for tentative in (1, 2):
                r = c.post(f"{base}/chat/completions", json=payload, headers=headers)
                if r.status_code == 429 and tentative == 1:
                    time.sleep(3)
                    continue
                if r.status_code == 429:
                    raise ErreurLLM("Modèle gratuit saturé (429) — réessaie dans un instant ou fournis ta propre clé.", code=429)
                if r.status_code >= 400:
                    code = 502 if r.status_code >= 500 else 422
                    raise ErreurLLM(f"Erreur fournisseur ({r.status_code}) : {r.text[:200]}", code=code)
                data = r.json()
                contenu = (data.get("choices") or [{}])[0].get("message", {}).get("content")
                if not contenu:
                    raise ErreurLLM("Le modèle a renvoyé une réponse vide.", code=502)
                return contenu.strip()
    except httpx.HTTPError as e:
        raise ErreurLLM(f"Fournisseur LLM injoignable : {str(e)[:150]}", code=502) from e
    except ValueError as e:
        raise ErreurLLM(f"Réponse du fournisseur illisible : {str(e)[:150]}", code=502) from e


def lister_modeles(base_url: str, cle: str) -> list[str]:
    """Liste les modèles disponibles chez un fournisseur OpenAI-compatible (BYOK)."""
    _valider_base_url(base_url)
    headers = {"Authorization": f"Bearer {cle}"}
    try:
        with httpx.Client(timeout=15) as c:
            r = c.get(f"{base_url.rstrip('/')}/models", headers=headers)
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPError as e:
        raise ErreurLLM(f"Impossible de récupérer les modèles : {str(e)[:150]}", code=502) from e
    except ValueError as e:
        raise ErreurLLM(f"Réponse du fournisseur illisible : {str(e)[:150]}", code=502) from e
    return sorted([m["id"] for m in data.get("data", []) if m.get("id")], key=lambda x: x.lower())
