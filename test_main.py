# test_main.py
from unittest.mock import patch

from fastapi.testclient import TestClient

import chunker
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


def _transcript_long():
    """Transcript synthétique assez long pour dépasser deux fois le budget par
    défaut du chunker (DEFAULT_MAX_TOKENS) et forcer plusieurs chunks réels."""
    entrees = [{"text": f"mot numero {i} " * 20, "start": float(i) * 3, "duration": 2.0}
               for i in range(300)]
    return {
        "video_id": "dQw4w9WgXcQ",
        "transcript": entrees,
        "langue": "fr",
        "titre": "Vidéo longue de test",
        "duree_minutes": 15.0,
    }


ANALYSE_FACTICE = """# 📺 ANALYSE VIDÉO : Vidéo longue de test
*Langue Source :* Français

## 🚀 Résumé Exécutif (TL;DR)
> Résumé court de ce chunk.

## 📍 Chapitrage Temporel
| Time | Sujet | Description |
| :--- | :--- | :--- |
| [00:10] | *Introduction* | Présentation du sujet |

## 💡 Top 3 Moments Forts (Insights)
1. *Point clé* [00:15] : Explication

## 📝 Résumé Détaillé
### 🔹 Contexte
Contenu de ce chunk.
"""


def test_sante():
    r = client.get("/sante")
    assert r.status_code == 200
    assert r.json()["service"] == "synopsis"


def test_modeles_sans_cle_renvoie_422():
    r = client.post("/modeles", json={"cle": "", "base_url": "https://api.exemple.com/v1"})
    assert r.status_code == 422


@patch("main.llm.lister_modeles", return_value=["a-model", "b-model"])
def test_modeles_avec_cle(mock_lister):
    r = client.post("/modeles", json={"cle": "sk-x", "base_url": "https://api.exemple.com/v1"})
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


@patch("main.fusion.fusionner", side_effect=main.llm.ErreurLLM("Modèle gratuit saturé — réessaie.", code=429))
@patch("main.extractor.transcript_youtube", return_value=_transcript_court())
@patch("main.llm.completer", return_value="## 📝 Résumé Détaillé\nContenu résumé.")
def test_resumer_erreur_fusion_renvoie_429_pas_500(mock_completer, mock_transcript, mock_fusion):
    """La fusion appelle aussi llm.completer en interne (Task 5) — une erreur LLM à
    cette étape doit rester une erreur explicite (le code porté par ErreurLLM),
    pas un 500 non géré."""
    r = client.post("/resumer", json={"url": "https://youtu.be/dQw4w9WgXcQ", "langue": "Français"})
    assert r.status_code == 429
    assert "saturé" in r.json()["detail"]


@patch("main.llm.completer", return_value="Oui, il est question de X.")
def test_qa(mock_completer):
    r = client.post("/qa", json={"contexte": "Résumé : la vidéo parle de X.", "question": "De quoi ça parle ?"})
    assert r.status_code == 200
    assert "X" in r.json()["reponse"]


def test_qa_sans_contexte_renvoie_422():
    r = client.post("/qa", json={"contexte": "", "question": "Quoi ?"})
    assert r.status_code == 422


@patch("main.extractor.transcript_youtube", return_value=_transcript_long())
@patch("main.llm.completer", return_value=ANALYSE_FACTICE)
def test_resumer_video_longue_exerce_le_vrai_decoupage_multi_chunks(mock_completer, mock_transcript):
    """Régression Finding 4 : le chunker RÉEL (non mocké) doit produire 3+ chunks
    sur cette vidéo longue, et main.py doit appeler llm.completer une fois par
    chunk réellement produit — pas juste une fois comme sur les fixtures courtes."""
    transcript_attendu = _transcript_long()["transcript"]
    chunks_attendus = chunker.chunk_transcript(transcript_attendu)
    assert len(chunks_attendus) >= 3, "le fixture doit forcer au moins 3 chunks réels"

    r = client.post("/resumer", json={"url": "https://youtu.be/dQw4w9WgXcQ", "langue": "Français"})
    assert r.status_code == 200
    # Un appel llm.completer par chunk réel produit par le vrai chunker, PLUS un
    # appel supplémentaire fait par fusion.fusionner elle-même pour refusionner
    # les corps de résumé (déclenché car il y a plus d'un chunk — voir fusion.py).
    assert mock_completer.call_count == len(chunks_attendus) + 1
    body = r.json()
    assert "Introduction" in body["rapport"]


@patch("main.chunker.chunk_transcript", return_value=[
    {"text": "chunk unique", "start": 0.0, "end": 2.0, "tokens": 10}])
@patch("main.extractor.transcript_youtube", return_value=_transcript_court())
@patch("main.llm.completer", return_value="## 📝 Résumé Détaillé\nContenu résumé.")
def test_resumer_propage_contexte_max_au_chunker(mock_completer, mock_transcript, mock_chunk):
    """Régression Finding 6 : un `contexte_max` fourni dans le `llm` de la requête
    doit atteindre `chunker.chunk_transcript` en tant que `max_tokens` — sinon le
    paramètre reste décoratif et n'est jamais réellement utilisable par BYOK."""
    r = client.post("/resumer", json={
        "url": "https://youtu.be/dQw4w9WgXcQ", "langue": "Français",
        "llm": {"contexte_max": 32000},
    })
    assert r.status_code == 200
    mock_chunk.assert_called_once()
    _, kwargs = mock_chunk.call_args
    assert kwargs["max_tokens"] == 32000


@patch("main.chunker.chunk_transcript", return_value=[
    {"text": "chunk unique", "start": 0.0, "end": 2.0, "tokens": 10}])
@patch("main.extractor.transcript_youtube", return_value=_transcript_court())
@patch("main.llm.completer", return_value="## 📝 Résumé Détaillé\nContenu résumé.")
def test_resumer_sans_contexte_max_garde_le_defaut(mock_completer, mock_transcript, mock_chunk):
    """Sans `contexte_max`, le chunker doit toujours recevoir le défaut sûr de 12000."""
    r = client.post("/resumer", json={"url": "https://youtu.be/dQw4w9WgXcQ", "langue": "Français"})
    assert r.status_code == 200
    _, kwargs = mock_chunk.call_args
    assert kwargs["max_tokens"] == chunker.DEFAULT_MAX_TOKENS


@patch("main.chunker.chunk_transcript", return_value=[
    {"text": "chunk unique", "start": 0.0, "end": 2.0, "tokens": 10}])
@patch("main.extractor.transcript_youtube", return_value=_transcript_court())
@patch("main.llm.completer", return_value="## 📝 Résumé Détaillé\nContenu résumé.")
def test_resumer_contexte_max_hors_bornes_est_ecrete(mock_completer, mock_transcript, mock_chunk):
    """Finding I1 : un `contexte_max` sous le plancher ou au-dessus du plafond doit
    être écrêté plutôt que transmis tel quel au chunker — sinon un appelant anonyme
    peut forcer des centaines de chunks (donc d'appels LLM) sur la clé d'instance."""
    r = client.post("/resumer", json={
        "url": "https://youtu.be/dQw4w9WgXcQ", "langue": "Français",
        "llm": {"contexte_max": 1},
    })
    assert r.status_code == 200
    _, kwargs = mock_chunk.call_args
    assert kwargs["max_tokens"] == 1000

    mock_chunk.reset_mock()
    r = client.post("/resumer", json={
        "url": "https://youtu.be/dQw4w9WgXcQ", "langue": "Français",
        "llm": {"contexte_max": 999999999},
    })
    assert r.status_code == 200
    _, kwargs = mock_chunk.call_args
    assert kwargs["max_tokens"] == 200000


@patch("main.extractor.transcript_youtube", return_value=_transcript_court())
def test_resumer_contexte_max_non_numerique_renvoie_422(mock_transcript):
    """Finding I1 : un `contexte_max` non numérique doit renvoyer une erreur 422
    propre, pas planter en 500 non géré dans le chunker."""
    r = client.post("/resumer", json={
        "url": "https://youtu.be/dQw4w9WgXcQ", "langue": "Français",
        "llm": {"contexte_max": "abc"},
    })
    assert r.status_code == 422


@patch("main.llm.lister_modeles", side_effect=main.llm.ErreurLLM("URL de fournisseur refusée (adresse privée/interne).", code=422))
def test_modeles_ssrf_renvoie_422_pas_502(mock_lister):
    """Finding I3 : un rejet SSRF (ErreurLLM, code=422) doit ressortir en 422, pas
    en 502 générique — cohérent avec /resumer et /qa sur la même exception."""
    r = client.post("/modeles", json={"cle": "sk-x", "base_url": "http://169.254.169.254/"})
    assert r.status_code == 422
    assert "privée" in r.json()["detail"]
