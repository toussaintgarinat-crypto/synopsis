# test_llm.py
import socket
from unittest.mock import MagicMock

import httpx
import pytest

import llm


@pytest.fixture(autouse=True)
def _dns_publique_par_defaut(monkeypatch):
    """Évite toute dépendance réseau réelle dans les tests : par défaut,
    `_valider_base_url` voit l'hôte résoudre vers une IP publique. Les tests
    SSRF ci-dessous surchargent explicitement ce mock pour simuler une IP privée."""
    monkeypatch.setattr(
        llm.socket, "getaddrinfo",
        lambda host, port: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))],
    )


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
    with pytest.raises(llm.ErreurLLM, match="Aucun modèle") as exc_info:
        llm.completer("prompt", None, max_tokens=100)
    assert exc_info.value.code == 422


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

    with pytest.raises(llm.ErreurLLM, match="saturé") as exc_info:
        llm.completer("prompt", {"base_url": "https://api.exemple.com/v1", "cle": "sk-x", "modele": "m"}, max_tokens=100)
    assert exc_info.value.code == 429


def test_completer_erreur_5xx_fournisseur_devient_502(monkeypatch):
    """Une panne côté fournisseur (5xx) est un problème amont, pas la faute de l'appelant."""
    reponse = MagicMock(status_code=503, text="service unavailable")
    mock_client = MagicMock()
    mock_client.__enter__.return_value.post.return_value = reponse
    monkeypatch.setattr(httpx, "Client", lambda **kw: mock_client)

    with pytest.raises(llm.ErreurLLM, match="Erreur fournisseur") as exc_info:
        llm.completer("prompt", {"base_url": "https://api.exemple.com/v1", "cle": "sk-x", "modele": "m"}, max_tokens=100)
    assert exc_info.value.code == 502


def test_completer_erreur_4xx_fournisseur_reste_422(monkeypatch):
    """Une erreur 4xx du fournisseur (mauvaise clé BYOK, mauvais nom de modèle) reste
    la faute de l'appelant."""
    reponse = MagicMock(status_code=400, text="bad request")
    mock_client = MagicMock()
    mock_client.__enter__.return_value.post.return_value = reponse
    monkeypatch.setattr(httpx, "Client", lambda **kw: mock_client)

    with pytest.raises(llm.ErreurLLM, match="Erreur fournisseur") as exc_info:
        llm.completer("prompt", {"base_url": "https://api.exemple.com/v1", "cle": "sk-x", "modele": "m"}, max_tokens=100)
    assert exc_info.value.code == 422


def test_completer_reponse_vide_devient_502(monkeypatch):
    reponse = MagicMock(status_code=200)
    reponse.json.return_value = {"choices": [{"message": {"content": ""}}]}
    mock_client = MagicMock()
    mock_client.__enter__.return_value.post.return_value = reponse
    monkeypatch.setattr(httpx, "Client", lambda **kw: mock_client)

    with pytest.raises(llm.ErreurLLM, match="réponse vide") as exc_info:
        llm.completer("prompt", {"base_url": "https://api.exemple.com/v1", "cle": "sk-x", "modele": "m"}, max_tokens=100)
    assert exc_info.value.code == 502


def test_lister_modeles_trie_les_ids(monkeypatch):
    reponse = MagicMock()
    reponse.json.return_value = {"data": [{"id": "z-model"}, {"id": "a-model"}]}
    reponse.raise_for_status.return_value = None

    mock_client = MagicMock()
    mock_client.__enter__.return_value.get.return_value = reponse
    monkeypatch.setattr(httpx, "Client", lambda **kw: mock_client)

    assert llm.lister_modeles("https://api.exemple.com/v1", "sk-x") == ["a-model", "z-model"]


def test_completer_erreur_transport_devient_erreurllm(monkeypatch):
    mock_client = MagicMock()
    mock_client.__enter__.return_value.post.side_effect = httpx.ConnectError("connection refused")
    monkeypatch.setattr(httpx, "Client", lambda **kw: mock_client)

    with pytest.raises(llm.ErreurLLM, match="injoignable") as exc_info:
        llm.completer("prompt", {"base_url": "https://api.exemple.com/v1", "cle": "sk-x", "modele": "m"}, max_tokens=100)
    assert exc_info.value.code == 502


def test_lister_modeles_erreur_http_devient_erreurllm(monkeypatch):
    reponse = MagicMock(status_code=401)
    reponse.raise_for_status.side_effect = httpx.HTTPStatusError(
        "401 Unauthorized", request=MagicMock(), response=MagicMock(status_code=401)
    )

    mock_client = MagicMock()
    mock_client.__enter__.return_value.get.return_value = reponse
    monkeypatch.setattr(httpx, "Client", lambda **kw: mock_client)

    with pytest.raises(llm.ErreurLLM, match="Impossible de récupérer les modèles") as exc_info:
        llm.lister_modeles("https://api.exemple.com/v1", "sk-x")
    assert exc_info.value.code == 502


def test_completer_refuse_ssrf_vers_ip_privee(monkeypatch):
    monkeypatch.setattr(
        llm.socket, "getaddrinfo",
        lambda host, port: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80))],
    )
    with pytest.raises(llm.ErreurLLM, match="refusée"):
        llm.completer("prompt", {"base_url": "http://127.0.0.1:8080/v1", "cle": "sk-x", "modele": "m"}, max_tokens=100)


def test_completer_refuse_ssrf_vers_ip_reseau_local(monkeypatch):
    monkeypatch.setattr(
        llm.socket, "getaddrinfo",
        lambda host, port: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.1", 80))],
    )
    with pytest.raises(llm.ErreurLLM, match="refusée"):
        llm.completer("prompt", {"base_url": "http://interne.exemple.com/v1", "cle": "sk-x", "modele": "m"}, max_tokens=100)


def test_lister_modeles_refuse_ssrf_vers_ip_privee(monkeypatch):
    monkeypatch.setattr(
        llm.socket, "getaddrinfo",
        lambda host, port: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80))],
    )
    with pytest.raises(llm.ErreurLLM, match="refusée"):
        llm.lister_modeles("http://127.0.0.1:8080/v1", "sk-x")


def test_lister_modeles_refuse_ssrf_vers_ip_reseau_local(monkeypatch):
    monkeypatch.setattr(
        llm.socket, "getaddrinfo",
        lambda host, port: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.1", 80))],
    )
    with pytest.raises(llm.ErreurLLM, match="refusée"):
        llm.lister_modeles("http://interne.exemple.com/v1", "sk-x")
