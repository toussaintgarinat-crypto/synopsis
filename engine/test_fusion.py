# engine/test_fusion.py
from unittest.mock import patch

import fusion

ANALYSE_1 = """# 📺 ANALYSE VIDÉO : Titre
*Langue Source :* Français

## 🚀 Résumé Exécutif (TL;DR)
> Un résumé court de la première moitié.

## 📍 Chapitrage Temporel
| Time | Sujet | Description |
| :--- | :--- | :--- |
| [00:10] | *Introduction* | Présentation du sujet |

## 💡 Top 3 Moments Forts (Insights)
1. *Point clé A* [00:15] : Explication A

## 📝 Résumé Détaillé
### 🔹 Contexte
Premier bloc de contenu.
"""

ANALYSE_2 = """# 📺 ANALYSE VIDÉO : Titre
*Langue Source :* Français

## 🚀 Résumé Exécutif (TL;DR)
> Un résumé court de la seconde moitié.

## 📍 Chapitrage Temporel
| Time | Sujet | Description |
| :--- | :--- | :--- |
| [05:00] | *Conclusion* | Synthèse finale |

## 💡 Top 3 Moments Forts (Insights)
1. *Point clé B* [05:05] : Explication B

## 📝 Résumé Détaillé
### 🔹 Conclusion
Second bloc de contenu.
"""


def test_fusionner_un_seul_chunk_renvoie_tel_quel():
    assert fusion.fusionner([ANALYSE_1], "Titre") == ANALYSE_1


def test_extraire_chapitres():
    chapitres = fusion._extraire_chapitres(ANALYSE_1)
    assert chapitres == [{"timestamp": "00:10", "ts_secondes": 10,
                           "sujet": "Introduction", "description": "Présentation du sujet"}]


def test_extraire_insights():
    insights = fusion._extraire_insights(ANALYSE_1)
    assert insights == [{"titre": "Point clé A", "timestamp": "00:15", "description": "Explication A"}]


@patch("llm.completer", return_value="### 🔹 Fusionné\nContenu fusionné cohérent.")
def test_fusionner_plusieurs_chunks(mock_completer):
    rapport = fusion.fusionner([ANALYSE_1, ANALYSE_2], "Titre", "Français")

    assert "Introduction" in rapport
    assert "Conclusion" in rapport
    assert "Point clé A" in rapport and "Point clé B" in rapport
    assert "Contenu fusionné cohérent." in rapport
    mock_completer.assert_called_once()


ANALYSE_CHAPITRE_TARDIF = """# 📺 ANALYSE VIDÉO : Titre
*Langue Source :* Français

## 🚀 Résumé Exécutif (TL;DR)
> Un résumé court.

## 📍 Chapitrage Temporel
| Time | Sujet | Description |
| :--- | :--- | :--- |
| [01:23:45] | *Chapitre tardif* | Description |

## 💡 Top 3 Moments Forts (Insights)
1. *Point clé tardif* [01:23:45] : Explication tardive

## 📝 Résumé Détaillé
### 🔹 Contexte
Contenu.
"""


def test_extraire_chapitres_timestamp_hh_mm_ss():
    """Régression : les vidéos de plus d'une heure produisent des timestamps
    HH:MM:SS (via chunker.format_timestamp) — ils ne doivent pas être perdus."""
    chapitres = fusion._extraire_chapitres(ANALYSE_CHAPITRE_TARDIF)
    assert chapitres == [{"timestamp": "01:23:45", "ts_secondes": 1 * 3600 + 23 * 60 + 45,
                           "sujet": "Chapitre tardif", "description": "Description"}]


def test_extraire_insights_timestamp_hh_mm_ss():
    """Régression équivalente pour les insights."""
    insights = fusion._extraire_insights(ANALYSE_CHAPITRE_TARDIF)
    assert insights == [{"titre": "Point clé tardif", "timestamp": "01:23:45",
                          "description": "Explication tardive"}]


ANALYSE_3 = """# 📺 ANALYSE VIDÉO : Titre
*Langue Source :* Français

## 🚀 Résumé Exécutif (TL;DR)
> Un résumé court de la troisième partie.

## 📍 Chapitrage Temporel
| Time | Sujet | Description |
| :--- | :--- | :--- |
| [10:00] | *Bonus* | Contenu bonus |

## 💡 Top 3 Moments Forts (Insights)
1. *Point clé C* [10:05] : Explication C

## 📝 Résumé Détaillé
### 🔹 Bonus
Troisième bloc de contenu.
"""


def test_selectionner_top_insights_round_robin_couvre_tous_les_chunks():
    """Avec 3 chunks et max_insights=3, la sélection doit prendre un insight par
    chunk (round-robin) plutôt que les 3 premiers du premier chunk."""
    listes = [
        [{"titre": "Début A"}, {"titre": "Début B"}, {"titre": "Début C"}],
        [{"titre": "Milieu A"}],
        [{"titre": "Fin A"}],
    ]
    choisis = fusion._selectionner_top_insights(listes, max_insights=3)
    titres = [i["titre"] for i in choisis]
    assert titres == ["Début A", "Milieu A", "Fin A"]


@patch("llm.completer", return_value="### 🔹 Fusionné\nContenu fusionné cohérent.")
def test_resume_executif_reste_borne_avec_plus_de_deux_chunks(mock_completer):
    """Avec 3+ chunks, le résumé exécutif ne doit pas concaténer tous les
    résumés (sinon un TL;DR de 20+ phrases sur une vidéo à 6 chunks) — seuls le
    premier et le dernier sont gardés."""
    rapport = fusion.fusionner([ANALYSE_1, ANALYSE_2, ANALYSE_3], "Titre", "Français")
    assert "Un résumé court de la première moitié." in rapport
    assert "Un résumé court de la troisième partie." in rapport
    assert "Un résumé court de la seconde moitié." not in rapport
