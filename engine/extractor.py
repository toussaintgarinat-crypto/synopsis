"""Extraction de transcript YouTube — sans téléchargement, sans ffmpeg.

Utilise le transcript natif (sous-titres, auto-générés ou non) via
`youtube_transcript_api`. Lève une erreur explicite si la vidéo n'a pas de
sous-titres — jamais de repli vers une transcription audio."""
from __future__ import annotations

import re

import httpx
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    CouldNotRetrieveTranscript,
    NoTranscriptFound,
    TranscriptsDisabled,
)

LANGUES_PAR_DEFAUT = ["fr", "en", "es", "de", "it", "pt"]


class ErreurExtraction(Exception):
    """Erreur explicite — URL invalide ou transcript indisponible."""


def extraire_id(url: str) -> str | None:
    """Extrait l'ID YouTube (11 caractères) depuis une URL ou un ID nu."""
    motifs = [
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})",
        r"^([a-zA-Z0-9_-]{11})$",
    ]
    for motif in motifs:
        m = re.search(motif, url.strip())
        if m:
            return m.group(1)
    return None


def titre_video(video_id: str) -> str:
    """Titre via l'API oembed publique — repli sur l'ID si indisponible."""
    try:
        r = httpx.get(
            "https://www.youtube.com/oembed",
            params={"url": f"https://www.youtube.com/watch?v={video_id}", "format": "json"},
            timeout=10,
        )
        if r.status_code == 200:
            return r.json().get("title") or f"Vidéo {video_id}"
    except httpx.HTTPError:
        pass
    return f"Vidéo {video_id}"


def transcript_youtube(url: str, langues: list[str] | None = None) -> dict:
    """URL YouTube → {video_id, transcript, langue, titre, duree_minutes}.

    `transcript` = [{text, start, duration}, ...]. Lève ErreurExtraction avec un
    message explicite si l'URL est invalide ou si la vidéo n'a pas de sous-titres."""
    video_id = extraire_id(url)
    if not video_id:
        raise ErreurExtraction(
            "URL YouTube invalide. Format attendu : youtube.com/watch?v=ID ou youtu.be/ID.")

    api = YouTubeTranscriptApi()
    langues = langues or LANGUES_PAR_DEFAUT
    brut = None
    langue_trouvee = None

    for langue in langues:
        try:
            brut = list(api.fetch(video_id, languages=[langue]))
            langue_trouvee = langue
            break
        except Exception:
            continue

    if brut is None:
        try:
            fetched = api.fetch(video_id)
            brut = list(fetched)
            langue_trouvee = getattr(fetched, "language_code", "unknown")
        except TranscriptsDisabled:
            raise ErreurExtraction("Les sous-titres sont désactivés sur cette vidéo.")
        except NoTranscriptFound:
            raise ErreurExtraction("Aucun sous-titre disponible pour cette vidéo.")
        except CouldNotRetrieveTranscript as e:
            raise ErreurExtraction(f"Sous-titres inaccessibles : {str(e)[:150]}")
        except Exception as e:
            raise ErreurExtraction(f"Erreur lors de la récupération des sous-titres : {str(e)[:150]}")

    if not brut:
        raise ErreurExtraction("Aucun sous-titre disponible pour cette vidéo.")

    transcript = [{"text": e.text, "start": e.start, "duration": e.duration} for e in brut]
    derniere = transcript[-1]
    duree_min = (derniere["start"] + derniere["duration"]) / 60

    return {
        "video_id": video_id,
        "transcript": transcript,
        "langue": langue_trouvee or "unknown",
        "titre": titre_video(video_id),
        "duree_minutes": duree_min,
    }
