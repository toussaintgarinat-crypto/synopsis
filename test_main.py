# test_main.py
from unittest.mock import patch

from fastapi.testclient import TestClient

import extractor
import main

client = TestClient(main.app)


def _transcript_court():
    return {
        "video_id": "dQw4w9WgXcQ",
        "transcript": [{"text": "Bonjour le monde", "start": 0.0, "duration": 2.0}],
        "langue": "fr",
        "titre": "Vidéo de test",
        "duree_minutes": 0.03,
    }


def test_sante():
    r = client.get("/sante")
    assert r.status_code == 200
    assert r.json()["service"] == "synopsis"


def test_modeles_sans_cle_renvoie_422():
    r = client.get("/modeles", params={"cle": "", "base_url": "https://api.exemple.com/v1"})
    assert r.status_code == 422


@patch("main.llm.lister_modeles", return_value=["a-model", "b-model"])
def test_modeles_avec_cle(mock_lister):
    r = client.get("/modeles", params={"cle": "sk-x", "base_url": "https://api.exemple.com/v1"})
    assert r.status_code == 200
    assert r.json() == {"modeles": ["a-model", "b-model"]}


@patch("main.extractor.transcript_youtube", return_value=_transcript_court())
@patch("main.llm.completer", return_value="## 📝 Résumé Détaillé\nContenu résumé.")
def test_resumer_video_valide(mock_completer, mock_transcript):
    r = client.post("/resumer", json={"url": "https://youtu.be/dQw4w9WgXcQ", "langue": "Français"})
    assert r.status_code == 200
    body = r.json()
    assert body["video_id"] == "dQw4w9WgXcQ"
    assert "Contenu résumé." in body["rapport"]


@patch("main.extractor.transcript_youtube", side_effect=extractor.ErreurExtraction("URL YouTube invalide."))
def test_resumer_url_invalide(mock_transcript):
    r = client.post("/resumer", json={"url": "pas-une-url", "langue": "Français"})
    assert r.status_code == 422
    assert "invalide" in r.json()["detail"]


@patch("main.fusion.fusionner", side_effect=main.llm.ErreurLLM("Modèle gratuit saturé — réessaie."))
@patch("main.extractor.transcript_youtube", return_value=_transcript_court())
@patch("main.llm.completer", return_value="## 📝 Résumé Détaillé\nContenu résumé.")
def test_resumer_erreur_fusion_renvoie_422_pas_500(mock_completer, mock_transcript, mock_fusion):
    """La fusion appelle aussi llm.completer en interne (Task 5) — une erreur LLM à
    cette étape doit rester un 422 explicite, pas un 500 non géré."""
    r = client.post("/resumer", json={"url": "https://youtu.be/dQw4w9WgXcQ", "langue": "Français"})
    assert r.status_code == 422
    assert "saturé" in r.json()["detail"]


@patch("main.llm.completer", return_value="Oui, il est question de X.")
def test_qa(mock_completer):
    r = client.post("/qa", json={"contexte": "Résumé : la vidéo parle de X.", "question": "De quoi ça parle ?"})
    assert r.status_code == 200
    assert "X" in r.json()["reponse"]


def test_qa_sans_contexte_renvoie_422():
    r = client.post("/qa", json={"contexte": "", "question": "Quoi ?"})
    assert r.status_code == 422
