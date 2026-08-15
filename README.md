# 📺 Synopsis

*[English version](README.en.md)*

Colle l'URL d'une vidéo YouTube : reçois un résumé structuré (chapitres horodatés,
points clés, résumé détaillé) en français ou dans 5 autres langues. Gratuit,
instantané, auto-hébergeable, déployable sur Vercel.

> Résumé généré par IA à partir des sous-titres — vérifie les points importants
> dans la vidéo source avant de t'y fier pour une décision.

## Essayer en ligne

**https://synopsis-jet.vercel.app** — sans clé, la démo publique répond mais `/resumer` demande une clé BYOK (aucune clé d'instance gratuite n'est configurée sur ce déploiement) ; colle la tienne dans « Options avancées ».

## Installation (auto-hébergée)

### Prérequis

- [Docker](https://docs.docker.com/get-docker/) + Docker Compose.
- `git`, `curl`.
- Port **8420** libre (changeable dans `docker-compose.yml`).

### En une commande

```bash
curl -fsSL https://raw.githubusercontent.com/toussaintgarinat-crypto/synopsis/main/install.sh | bash
```

### Ou manuellement

```bash
git clone https://github.com/toussaintgarinat-crypto/synopsis.git
cd synopsis
docker compose up -d --build
```

Vérifier :

```bash
curl http://localhost:8420/sante
```

Puis ouvrir **http://localhost:8420**.

**Sans Docker** (dev local) :

```bash
pip install -r requirements-dev.txt
uvicorn main:app --reload --port 8420
```

## Ce que tu obtiens

- Résumé structuré : résumé exécutif, chapitrage temporel horodaté, 3 points clés,
  résumé détaillé.
- 6 langues : Français, English, Español, Deutsch, Português, Italiano.
- Chat sur le contenu déjà résumé.
- Plusieurs vidéos d'un coup (colle plusieurs liens, une par ligne).
- Export HTML / Markdown / PDF (impression), 100% navigateur.

## Coût réel : zéro (par défaut)

Le transcript est le sous-titrage natif YouTube — aucun téléchargement, aucun
ffmpeg, aucun Whisper. Seul le résumé passe par un LLM.

## Configurer un LLM

Deux façons, au choix :

1. **Clé personnelle (BYOK)** : dans « Options avancées » du formulaire, choisis un
   fournisseur (OpenRouter, OpenCode Go, OpenAI, ou personnalisé), colle ta clé.
   Elle est sauvegardée uniquement dans ton navigateur (`localStorage`), jamais sur
   le serveur.
2. **Clé d'instance** (si tu auto-héberges) : renseigne `OPENROUTER_API_KEY` (ou
   `OPENCODE_GO_API_KEY` / `OPENAI_API_KEY`) dans `.env` (voir `.env.example`) —
   active un modèle gratuit par défaut pour tous les visiteurs de ton instance.

Sans aucune des deux, `/resumer` et `/qa` répondent une erreur explicite — jamais
de résumé inventé.

## Limites (V1)

- YouTube uniquement (pas Twitch/Vimeo/TikTok/fichiers) — nécessite des
  sous-titres (auto-générés ou non) sur la vidéo.
- Pas de vraie playlist YouTube (l'énumération demanderait une clé YouTube Data
  API) — colle plusieurs liens à la place.
- Pas de transcription audio (Whisper) — incompatible avec un déploiement
  serverless sans disque persistant.

## Licence

Apache 2.0 — voir `LICENSE` et `NOTICE`.
