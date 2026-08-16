from unittest.mock import MagicMock, patch

import pytest

import extractor


def test_extraire_id_watch_url():
    assert extractor.extraire_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_extraire_id_short_url():
    assert extractor.extraire_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_extraire_id_embed_url():
    assert extractor.extraire_id("https://www.youtube.com/embed/dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_extraire_id_id_nu():
    assert extractor.extraire_id("dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_extraire_id_invalide():
    assert extractor.extraire_id("https://example.com/pas-une-video") is None


def test_transcript_youtube_url_invalide():
    with pytest.raises(extractor.ErreurExtraction, match="URL YouTube invalide"):
        extractor.transcript_youtube("https://example.com/pas-une-video")


def _entree(text, start, duration):
    e = MagicMock()
    e.text, e.start, e.duration = text, start, duration
    return e


@patch("extractor.titre_video", return_value="Vidéo de test")
@patch("extractor.YouTubeTranscriptApi")
def test_transcript_youtube_succes(mock_api_cls, mock_titre):
    mock_api = MagicMock()
    mock_api.fetch.return_value = [_entree("Bonjour", 0.0, 2.0), _entree("le monde", 2.0, 1.5)]
    mock_api_cls.return_value = mock_api

    resultat = extractor.transcript_youtube("https://youtu.be/dQw4w9WgXcQ", langues=["fr"])

    assert resultat["video_id"] == "dQw4w9WgXcQ"
    assert resultat["titre"] == "Vidéo de test"
    assert resultat["transcript"] == [
        {"text": "Bonjour", "start": 0.0, "duration": 2.0},
        {"text": "le monde", "start": 2.0, "duration": 1.5},
    ]
    assert resultat["duree_minutes"] == pytest.approx(3.5 / 60)


@patch("extractor.YouTubeTranscriptApi")
def test_transcript_youtube_sous_titres_desactives(mock_api_cls):
    from youtube_transcript_api._errors import TranscriptsDisabled

    mock_api = MagicMock()
    mock_api.fetch.side_effect = TranscriptsDisabled("dQw4w9WgXcQ")
    mock_api_cls.return_value = mock_api

    with pytest.raises(extractor.ErreurExtraction, match="désactivés"):
        extractor.transcript_youtube("https://youtu.be/dQw4w9WgXcQ", langues=["fr"])


@patch("extractor.YouTubeTranscriptApi")
def test_transcript_youtube_sous_titres_desactives_mentionne_version_locale(mock_api_cls):
    """Sans transcript, aucun repli Whisper n'existe sur cette instance — le message
    doit pointer explicitement vers la version locale qui en a un, pas juste dire
    non sans piste de sortie."""
    from youtube_transcript_api._errors import TranscriptsDisabled

    mock_api = MagicMock()
    mock_api.fetch.side_effect = TranscriptsDisabled("dQw4w9WgXcQ")
    mock_api_cls.return_value = mock_api

    with pytest.raises(extractor.ErreurExtraction, match=extractor.URL_VERSION_LOCALE):
        extractor.transcript_youtube("https://youtu.be/dQw4w9WgXcQ", langues=["fr"])


@patch("extractor.YouTubeTranscriptApi")
def test_transcript_youtube_aucune_langue_disponible(mock_api_cls):
    """Aucune des langues demandées n'a de sous-titre (mais pas globalement désactivés)."""
    from youtube_transcript_api._errors import NoTranscriptFound

    mock_api = MagicMock()
    # NoTranscriptFound requires: video_id, requested_language_codes, transcript_data
    mock_api.fetch.side_effect = NoTranscriptFound(
        "dQw4w9WgXcQ", ["fr", "en"], MagicMock()
    )
    mock_api_cls.return_value = mock_api

    with pytest.raises(
        extractor.ErreurExtraction,
        match="Aucun sous-titre disponible dans les langues demandées",
    ):
        extractor.transcript_youtube("https://youtu.be/dQw4w9WgXcQ", langues=["fr", "en"])
