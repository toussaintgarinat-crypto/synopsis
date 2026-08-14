# test_llm.py
from unittest.mock import MagicMock

import httpx
import pytest

import llm


def test_config_priorite_byok():
    base, cle, modele = llm.config({"base_url": "https://api.exemple.com/v1", "cle": "sk-xxx", "modele": "gpt-x"})
    assert (base, cle, modele) == ("https://api.exemple.com/v1", "sk-xxx", "gpt-x")


def test_config_priorite_openrouter_instance(monkeypatch):
    monkeypatch.setattr(llm, "OPENROUTER_API_KEY", "sk-or-instance")
    base, cle, modele = llm.config(None)
    assert base == llm.OPENROUTER_BASE
    assert cle == "sk-or-instance"
    assert modele == llm.OPENROUTER_MODEL


def test_config_rien_configure(monkeypatch):
    monkeypatch.setattr(llm, "OPENROUTER_API_KEY", "")
    monkeypatch.setattr(llm, "OPENCODE_GO_API_KEY", "")
    monkeypatch.setattr(llm, "OPENAI_API_KEY", "")
    base, cle, modele = llm.config(None)
    assert (base, cle, modele) == ("", "", "")


def test_completer_leve_si_rien_configure(monkeypatch):
    monkeypatch.setattr(llm, "OPENROUTER_API_KEY", "")
    monkeypatch.setattr(llm, "OPENCODE_GO_API_KEY", "")
    monkeypatch.setattr(llm, "OPENAI_API_KEY", "")
    with pytest.raises(llm.ErreurLLM, match="Aucun modèle"):
        llm.completer("prompt", None, max_tokens=100)


def test_completer_appelle_le_fournisseur(monkeypatch):
    reponse = MagicMock(status_code=200)
    reponse.json.return_value = {"choices": [{"message": {"content": "  Résultat  "}}]}

    mock_client = MagicMock()
    mock_client.__enter__.return_value.post.return_value = reponse
    monkeypatch.setattr(httpx, "Client", lambda **kw: mock_client)

    texte = llm.completer("prompt", {"base_url": "https://api.exemple.com/v1", "cle": "sk-x", "modele": "m"}, max_tokens=100)
    assert texte == "Résultat"


def test_completer_429_puis_succes_second_essai(monkeypatch):
    reponse_429 = MagicMock(status_code=429, text="rate limited")
    reponse_ok = MagicMock(status_code=200)
    reponse_ok.json.return_value = {"choices": [{"message": {"content": "Résultat"}}]}

    mock_client = MagicMock()
    mock_client.__enter__.return_value.post.side_effect = [reponse_429, reponse_ok]
    monkeypatch.setattr(httpx, "Client", lambda **kw: mock_client)
    monkeypatch.setattr(llm.time, "sleep", lambda *_: None)

    texte = llm.completer("prompt", {"base_url": "https://api.exemple.com/v1", "cle": "sk-x", "modele": "m"}, max_tokens=100)
    assert texte == "Résultat"


def test_completer_429_persistant_leve_erreur_explicite(monkeypatch):
    reponse = MagicMock(status_code=429, text="rate limited")

    mock_client = MagicMock()
    mock_client.__enter__.return_value.post.return_value = reponse
    monkeypatch.setattr(httpx, "Client", lambda **kw: mock_client)
    monkeypatch.setattr(llm.time, "sleep", lambda *_: None)

    with pytest.raises(llm.ErreurLLM, match="saturé"):
        llm.completer("prompt", {"base_url": "https://api.exemple.com/v1", "cle": "sk-x", "modele": "m"}, max_tokens=100)


def test_lister_modeles_trie_les_ids(monkeypatch):
    reponse = MagicMock()
    reponse.json.return_value = {"data": [{"id": "z-model"}, {"id": "a-model"}]}
    reponse.raise_for_status.return_value = None

    mock_client = MagicMock()
    mock_client.__enter__.return_value.get.return_value = reponse
    monkeypatch.setattr(httpx, "Client", lambda **kw: mock_client)

    assert llm.lister_modeles("https://api.exemple.com/v1", "sk-x") == ["a-model", "z-model"]
