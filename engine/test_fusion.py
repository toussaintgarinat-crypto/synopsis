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
