"""Découpage d'un transcript en chunks sous la limite de tokens du modèle actif."""
from __future__ import annotations

import tiktoken

DEFAULT_MAX_TOKENS = 12000
DEFAULT_OVERLAP_TOKENS = 1200


def estimate_tokens(text: str) -> int:
    """Estimation via l'encodage cl100k_base — bonne approximation pour la plupart des modèles."""
    try:
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return len(text) // 4


def format_timestamp(seconds: float) -> str:
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    if minutes >= 60:
        hours, minutes = minutes // 60, minutes % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def create_text_from_transcript(transcript: list[dict]) -> str:
    return "\n".join(f"[{format_timestamp(e['start'])}] {e['text']}" for e in transcript)


def chunk_transcript(transcript: list[dict], max_tokens: int = DEFAULT_MAX_TOKENS,
                      overlap_tokens: int = DEFAULT_OVERLAP_TOKENS) -> list[dict]:
    """Découpe un transcript [{text, start, duration}] en chunks
    [{text, start, end, tokens}] sous `max_tokens`, avec un recouvrement entre chunks
    pour ne pas couper le contexte en plein milieu d'une idée."""
    if not transcript:
        return []

    texte_complet = create_text_from_transcript(transcript)
    total_tokens = estimate_tokens(texte_complet)

    if total_tokens <= max_tokens:
        return [{"text": texte_complet, "start": transcript[0]["start"],
                  "end": transcript[-1]["start"] + transcript[-1].get("duration", 0),
                  "tokens": total_tokens}]

    chunks = []
    position = 0
    while position < len(transcript):
        entrees_chunk, tokens_chunk = [], 0
        debut_chunk = transcript[position]["start"]

        for i in range(position, len(transcript)):
            entree = transcript[i]
            texte_entree = f"[{format_timestamp(entree['start'])}] {entree['text']}"
            tokens_entree = estimate_tokens(texte_entree)
            if tokens_chunk + tokens_entree > max_tokens and entrees_chunk:
                break
            entrees_chunk.append(entree)
            tokens_chunk += tokens_entree

        derniere = entrees_chunk[-1]
        fin_chunk = derniere["start"] + derniere.get("duration", 0)
        chunks.append({"text": create_text_from_transcript(entrees_chunk), "start": debut_chunk,
                        "end": fin_chunk, "tokens": tokens_chunk})

        if position + len(entrees_chunk) >= len(transcript):
            break

        chevauchement = max(1, len(entrees_chunk) // 10)
        prochaine_position = min(position + len(entrees_chunk) - chevauchement, len(transcript) - 1)
        if prochaine_position <= position:
            prochaine_position = position + 1
        position = prochaine_position

    return chunks
