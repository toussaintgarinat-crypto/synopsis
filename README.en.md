# 📺 Synopsis

*[Version française](README.md)*

Paste a YouTube video URL: get a structured summary (timestamped chapters, key
points, detailed summary) in French or 5 other languages. Free, instant,
self-hostable, deployable on Vercel.

> AI-generated summary based on captions — double-check anything important
> against the source video before relying on it.

## Try it online

*(to be filled in after the Vercel deployment — Task 12)*

## Installation (self-hosted)

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) + Docker Compose.
- `git`, `curl`.
- Free port **8420** (changeable in `docker-compose.yml`).

### One command

```bash
curl -fsSL https://raw.githubusercontent.com/toussaintgarinat-crypto/synopsis/main/install.sh | bash
```

### Or manually

```bash
git clone https://github.com/toussaintgarinat-crypto/synopsis.git
cd synopsis
docker compose up -d --build
```

Check:

```bash
curl http://localhost:8420/sante
```

Then open **http://localhost:8420**.

**Without Docker** (local dev):

```bash
pip install -r requirements-dev.txt
uvicorn main:app --reload --port 8420
```

## What you get

- Structured summary: executive summary, timestamped chapters, 3 key highlights,
  detailed summary.
- 6 languages: French, English, Spanish, German, Portuguese, Italian.
- Chat about the already-summarized content.
- Multiple videos at once (paste several links, one per line).
- HTML / Markdown / PDF export (print), 100% browser-side.

## Real cost: zero (by default)

The transcript comes from YouTube's native captions — no download, no ffmpeg, no
Whisper. Only the summary itself goes through an LLM.

## Configuring an LLM

Two options:

1. **Personal key (BYOK)**: in the form's "Advanced options", pick a provider
   (OpenRouter, OpenCode Go, OpenAI, or custom), paste your key. It's saved only
   in your browser (`localStorage`), never on the server.
2. **Instance key** (if self-hosting): set `OPENROUTER_API_KEY` (or
   `OPENCODE_GO_API_KEY` / `OPENAI_API_KEY`) in `.env` (see `.env.example`) —
   enables a free default model for every visitor of your instance.

Without either, `/resumer` and `/qa` return an explicit error — never a made-up
summary.

## Limitations (V1)

- YouTube only (no Twitch/Vimeo/TikTok/file upload) — requires captions
  (auto-generated or not) on the video.
- No real playlist support (enumerating one would require a YouTube Data API key)
  — paste multiple links instead.
- No audio transcription (Whisper) — incompatible with a serverless deployment
  without persistent disk.

## License

Apache 2.0 — see `LICENSE` and `NOTICE`.
