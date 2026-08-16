# main.py
"""Synopsis — résumé de vidéo YouTube par IA.

Transcript natif YouTube (pas de téléchargement, pas de ffmpeg, pas de Whisper) →
découpage en chunks → résumé par chunk (LLM) → fusion en un rapport unique
(chapitres horodatés + points clés). Stateless : rien n'est stocké, chaque appel
est indépendant. LLM gratuit par défaut (clé OpenRouter d'instance) ou BYOK par
requête — jamais de résumé inventé si aucun modèle n'est configuré."""
import os
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent / "engine"))

import analyzer as prompt_analyzer
import chunker
import extractor
import fusion

import llm

app = FastAPI(title="Synopsis", version="0.1.0")

# Au-delà, le pipeline (extraction + N appels LLM séquentiels + fusion) dépasse la
# limite de 60s d'une fonction serverless Vercel — mesuré empiriquement avec le
# modèle gratuit d'instance : ~30-34s par appel LLM sur un chunk plein (12000
# tokens), donc dès 2 chunks + fusion (3 appels) le budget est dépassé à coup sûr.
# Un seul chunk (~12000 tokens, atteint vers 30-40 min de vidéo selon la densité de
# parole) reste sous la limite. On coupe à 30 min pour rester dans la zone sûre.
DUREE_MAX_MINUTES = 30

_cors = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()] or ["*"]
app.add_middleware(CORSMiddleware, allow_origins=_cors, allow_methods=["*"], allow_headers=["*"])


class ResumerBody(BaseModel):
    url: str
    langue: str = "Français"
    llm: Optional[dict] = None


class QaBody(BaseModel):
    contexte: str
    question: str
    llm: Optional[dict] = None


class ModelesBody(BaseModel):
    cle: str
    base_url: str = ""


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def accueil():
    return Path(__file__).parent.joinpath("static/index.html").read_text(encoding="utf-8")


@app.get("/sante", tags=["système"])
def sante():
    fournisseur = None
    if llm.OPENROUTER_API_KEY:
        fournisseur = "openrouter"
    elif llm.OPENCODE_GO_API_KEY:
        fournisseur = "opencode-go"
    elif llm.OPENAI_API_KEY:
        fournisseur = "openai"
    return {"statut": "ok", "service": "synopsis", "version": app.version,
            "resume_configure": bool(fournisseur), "fournisseur_actif": fournisseur,
            "duree_max_minutes": DUREE_MAX_MINUTES}


@app.post("/modeles", tags=["synopsis"])
def modeles(body: ModelesBody):
    """Liste les modèles disponibles pour une API OpenAI-compatible (BYOK)."""
    cle = body.cle.strip()
    if not cle:
        raise HTTPException(422, "Une clé API est nécessaire.")
    base = (body.base_url or "").strip()
    if not base:
        raise HTTPException(422, "Une URL de base est nécessaire.")
    try:
        return {"modeles": llm.lister_modeles(base, cle)}
    except llm.ErreurLLM as e:
        raise HTTPException(e.code, str(e))
    except Exception as e:
        raise HTTPException(502, f"Impossible de récupérer les modèles : {str(e)[:150]}")


@app.post("/resumer", tags=["synopsis"])
def resumer(body: ResumerBody):
    """URL YouTube → transcript natif → chunks → résumé par chunk → fusion."""
    try:
        donnees = extractor.transcript_youtube(body.url)
    except extractor.ErreurExtraction as e:
        raise HTTPException(422, str(e))

    if donnees["duree_minutes"] > DUREE_MAX_MINUTES:
        raise HTTPException(422,
            f"Vidéo trop longue pour cette instance en ligne "
            f"({donnees['duree_minutes']:.0f} min, limite {DUREE_MAX_MINUTES} min) — "
            f"au-delà, le résumé dépasse la limite de temps du serveur (Vercel, 60s) et "
            f"échoue silencieusement. Utilise la version locale (Whisper, sans limite de "
            f"durée) : {extractor.URL_VERSION_LOCALE}")

    contexte_max_brut = (body.llm or {}).get("contexte_max")
    contexte_max = chunker.DEFAULT_MAX_TOKENS
    if contexte_max_brut is not None:
        try:
            contexte_max = max(1000, min(200000, int(contexte_max_brut)))
        except (TypeError, ValueError):
            raise HTTPException(422, "contexte_max doit être un entier.")
    chunks = chunker.chunk_transcript(donnees["transcript"], max_tokens=contexte_max)
    if not chunks:
        raise HTTPException(422, "Transcript vide — impossible de résumer.")

    analyses = []
    for c in chunks:
        prompt = prompt_analyzer.preparer_prompt(c["text"], donnees["titre"], body.langue)
        try:
            analyses.append(llm.completer(prompt, body.llm, max_tokens=4000, temperature=0.5))
        except llm.ErreurLLM as e:
            raise HTTPException(e.code, str(e))

    try:
        rapport = fusion.fusionner(analyses, donnees["titre"], body.langue, body.llm)
    except llm.ErreurLLM as e:
        raise HTTPException(e.code, str(e))
    return {"video_id": donnees["video_id"], "titre": donnees["titre"],
            "langue_source": donnees["langue"], "duree_minutes": donnees["duree_minutes"],
            "rapport": rapport}


@app.post("/qa", tags=["synopsis"])
def qa(body: QaBody):
    """Question sur un résumé déjà généré — un seul appel LLM, rien stocké."""
    if not body.contexte.strip() or not body.question.strip():
        raise HTTPException(422, "Contexte et question sont requis.")
    prompt = (
        "Tu réponds à une question sur le contenu d'une vidéo, en te basant "
        "UNIQUEMENT sur le résumé fourni ci-dessous. N'invente rien qui n'y figure "
        "pas ; si la réponse n'est pas dans le résumé, dis-le clairement.\n\n"
        f"RÉSUMÉ :\n{body.contexte}\n\nQUESTION : {body.question}"
    )
    try:
        return {"reponse": llm.completer(prompt, body.llm, max_tokens=800, temperature=0.3)}
    except llm.ErreurLLM as e:
        raise HTTPException(e.code, str(e))
