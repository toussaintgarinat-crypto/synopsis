# engine/fusion.py
"""Fusion de résumés partiels en un rapport final.

Chapitrage et points clés sont fusionnés par du code (dédoublonnage, tri
chronologique) ; seul le résumé détaillé est refusionné par le LLM, à partir du
gabarit `prompts/fusion.xml`."""
from __future__ import annotations

import re
from pathlib import Path

import llm

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def charger_prompt_fusion() -> str:
    return (_PROMPTS_DIR / "fusion.xml").read_text(encoding="utf-8")


def _formater(gabarit: str, **kw) -> str:
    for cle, val in kw.items():
        gabarit = gabarit.replace("{" + cle + "}", str(val))
    return gabarit


def _extraire_chapitres(analyse: str) -> list[dict]:
    """Extrait les lignes du tableau `## 📍 Chapitrage Temporel`."""
    chapitres = []
    if not analyse:
        return chapitres
    motif_section = r"##\s*📍\s*Chapitrage\s*Temporel\s*\n(.*?)(?=\n##\s|\Z)"
    m = re.search(motif_section, analyse, re.DOTALL | re.IGNORECASE)
    if not m:
        return chapitres
    section = m.group(1)
    motif_ligne = r"\|\s*\[?(\d{1,3}:\d{2})\]?\s*\|\s*\*?(.+?)\*?\s*\|\s*(.+?)\s*\|"
    for ligne in re.finditer(motif_ligne, section):
        ts_brut = ligne.group(1)
        sujet = ligne.group(2).strip().rstrip("*").lstrip("*")
        desc = ligne.group(3).strip()
        if sujet.startswith(":") and desc.startswith(":"):
            continue
        parts = ts_brut.split(":")
        ts_secondes = int(parts[0]) * 60 + int(parts[1])
        chapitres.append({"timestamp": ts_brut, "ts_secondes": ts_secondes,
                           "sujet": sujet, "description": desc})
    return chapitres


def _extraire_insights(analyse: str) -> list[dict]:
    """Extrait les entrées de `## 💡 Top 3 Moments Forts`."""
    insights = []
    if not analyse:
        return insights
    motif_section = r"##\s*💡\s*Top\s*\d*\s*Moments\s*Forts.*?\n(.*?)(?=\n##\s|\Z)"
    m = re.search(motif_section, analyse, re.DOTALL | re.IGNORECASE)
    if not m:
        return insights
    section = m.group(1)
    motif_item = r"\d+\.\s*\*?(.+?)\*?\s*\[?(\d{1,3}:\d{2})\]?\s*:\s*(.+)"
    for item in re.finditer(motif_item, section):
        insights.append({"titre": item.group(1).strip().rstrip("*").lstrip("*"),
                          "timestamp": item.group(2), "description": item.group(3).strip()})
    return insights


def _extraire_corps_resume(analyse: str) -> str:
    m = re.search(r"##\s*📝\s*Résumé\s*Détaillé\s*\n(.*)", analyse, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else ""


def _extraire_resume_executif(analyse: str) -> str:
    m = re.search(r"##\s*🚀\s*Résumé\s*Exécutif.*?\n>\s*(.*?)(?=\n##\s|\n\*\*|\Z)",
                  analyse, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else ""


def _fusionner_chapitres(listes: list[list[dict]]) -> list[dict]:
    tous = [c for l in listes for c in l]
    tous.sort(key=lambda x: x.get("ts_secondes", 0))
    vus, uniques = set(), []
    for c in tous:
        ts = c.get("ts_secondes", 0)
        if ts not in vus:
            vus.add(ts)
            uniques.append(c)
    return uniques


def _selectionner_top_insights(listes: list[list[dict]], max_insights: int = 3) -> list[dict]:
    tous, vus = [], set()
    for l in listes:
        for ins in l:
            cle = ins.get("titre", "").lower()
            if cle and cle not in vus:
                vus.add(cle)
                tous.append(ins)
    return tous[:max_insights]


def _table_chapitres_markdown(chapitres: list[dict]) -> str:
    if not chapitres:
        return ""
    lignes = ["## 📍 Chapitrage Temporel", "| Time | Sujet | Description |", "| :--- | :--- | :--- |"]
    for c in chapitres:
        lignes.append(f"| {c.get('timestamp', '')} | *{c.get('sujet', '')}* | {c.get('description', '')} |")
    return "\n".join(lignes)


def _liste_insights_markdown(insights: list[dict]) -> str:
    if not insights:
        return ""
    lignes = ["## 💡 Top 3 Moments Forts (Insights)"]
    for i, ins in enumerate(insights, 1):
        lignes.append(f"{i}. *{ins.get('titre', '')}* [{ins.get('timestamp', '')}] : {ins.get('description', '')}")
    return "\n".join(lignes)


def fusionner(analyses: list[str], titre_video: str, langue: str = "Français",
              llm_body: dict | None = None) -> str:
    """Fusionne plusieurs analyses partielles (une par chunk) en un rapport unique.

    Chapitrage et insights sont fusionnés par code (dédoublonnés, triés). Le résumé
    détaillé est refusionné par le LLM à partir de `prompts/fusion.xml` — si un seul
    chunk existe, on renvoie l'analyse telle quelle (rien à fusionner)."""
    if len(analyses) == 1:
        return analyses[0]

    listes_chapitres, listes_insights, corps, execs = [], [], [], []
    for a in analyses:
        if not a:
            continue
        listes_chapitres.append(_extraire_chapitres(a))
        listes_insights.append(_extraire_insights(a))
        c = _extraire_corps_resume(a)
        if c:
            corps.append(c)
        e = _extraire_resume_executif(a)
        if e:
            execs.append(e)

    chapitres_fusionnes = _fusionner_chapitres(listes_chapitres)
    insights_choisis = _selectionner_top_insights(listes_insights)
    resume_exec = " ".join(execs) if execs else "Analyse de la vidéo."

    if corps:
        prompt = _formater(charger_prompt_fusion(), video_title=titre_video,
                            output_language=langue, analyses="\n\n---\n\n".join(corps))
        resume_detaille = llm.completer(prompt, llm_body, max_tokens=6000, temperature=0.5)
    else:
        resume_detaille = analyses[0]

    corps_final = resume_detaille.strip()
    for prefixe in ("## 📝 Résumé Détaillé", "## 📝 Résumé Détaille"):
        if corps_final.startswith(prefixe):
            corps_final = corps_final[len(prefixe):].strip()

    parties = [
        f"# 📺 ANALYSE VIDÉO : {titre_video}",
        f"*Langue Source :* {langue}\n",
        "## 🚀 Résumé Exécutif (TL;DR)",
        f"> {resume_exec.strip()}\n",
        _table_chapitres_markdown(chapitres_fusionnes),
        "",
        _liste_insights_markdown(insights_choisis),
        "",
        "## 📝 Résumé Détaillé",
        corps_final,
    ]
    return "\n\n".join(p for p in parties if p)
