"""Prépare le prompt d'analyse par chunk à partir du gabarit prompts/analyzer.xml."""
from __future__ import annotations

from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def charger_prompt_analyse() -> str:
    return (_PROMPTS_DIR / "analyzer.xml").read_text(encoding="utf-8")


def _formater(gabarit: str, **kw) -> str:
    for cle, val in kw.items():
        gabarit = gabarit.replace("{" + cle + "}", str(val))
    return gabarit


def preparer_prompt(transcript_chunk: str, titre_video: str, langue: str = "Français") -> str:
    return _formater(charger_prompt_analyse(), video_title=titre_video,
                      transcript=transcript_chunk, output_language=langue)
