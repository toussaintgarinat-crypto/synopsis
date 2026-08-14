# llm.py
"""Adaptateur LLM — résumé de transcript vidéo.

Priorité : BYOK par requête > clé d'instance OpenRouter > OpenCode Go > OpenAI-
compatible > repli honnête (erreur explicite, jamais de résumé inventé)."""
from __future__ import annotations

import os
import time

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


def completer(prompt: str, llm: dict | None, max_tokens: int, temperature: float = 0.5) -> str:
    """Un appel chat-completion, avec un seul retry court sur 429."""
    base, cle, modele = config(llm)
    if not cle or not modele:
        raise ErreurLLM("Aucun modèle LLM configuré (ni BYOK, ni clé par défaut de l'instance).")
    headers = {"Authorization": f"Bearer {cle}"}
    payload = {"model": modele, "temperature": temperature, "max_tokens": max_tokens,
               "messages": [{"role": "user", "content": prompt}]}
    with httpx.Client(timeout=120) as c:
        for tentative in (1, 2):
            r = c.post(f"{base}/chat/completions", json=payload, headers=headers)
            if r.status_code == 429 and tentative == 1:
                time.sleep(3)
                continue
            if r.status_code == 429:
                raise ErreurLLM("Modèle gratuit saturé (429) — réessaie dans un instant ou fournis ta propre clé.")
            if r.status_code >= 400:
                raise ErreurLLM(f"Erreur fournisseur ({r.status_code}) : {r.text[:200]}")
            data = r.json()
            contenu = (data.get("choices") or [{}])[0].get("message", {}).get("content")
            if not contenu:
                raise ErreurLLM("Le modèle a renvoyé une réponse vide.")
            return contenu.strip()
    raise ErreurLLM("Modèle gratuit saturé — réessaie dans un instant ou fournis ta propre clé.")


def lister_modeles(base_url: str, cle: str) -> list[str]:
    """Liste les modèles disponibles chez un fournisseur OpenAI-compatible (BYOK)."""
    headers = {"Authorization": f"Bearer {cle}"}
    with httpx.Client(timeout=15) as c:
        r = c.get(f"{base_url.rstrip('/')}/models", headers=headers)
        r.raise_for_status()
        data = r.json()
    return sorted([m["id"] for m in data.get("data", []) if m.get("id")], key=lambda x: x.lower())
