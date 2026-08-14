import analyzer


def test_preparer_prompt_injecte_les_valeurs():
    prompt = analyzer.preparer_prompt("Bonjour le monde", "Ma Vidéo", "English")
    assert "Ma Vidéo" in prompt
    assert "Bonjour le monde" in prompt
    assert "English" in prompt


def test_preparer_prompt_ne_casse_pas_sur_accolades_dans_le_transcript():
    prompt = analyzer.preparer_prompt("Un texte avec { des accolades }", "Titre", "Français")
    assert "{ des accolades }" in prompt
