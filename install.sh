#!/usr/bin/env bash
# Installe et lance Synopsis en une seule commande :
#
#   curl -fsSL https://raw.githubusercontent.com/toussaintgarinat-crypto/synopsis/main/install.sh | bash
#
set -euo pipefail

REPO_URL="https://github.com/toussaintgarinat-crypto/synopsis.git"
DEST="${SYNOPSIS_DIR:-synopsis}"
PORT=8420

info()  { printf '\033[1;36m→ %s\033[0m\n' "$1"; }
ok()    { printf '\033[1;32m✓ %s\033[0m\n' "$1"; }
fail()  { printf '\033[1;31m✗ %s\033[0m\n' "$1" >&2; exit 1; }

command -v git >/dev/null 2>&1 || fail "git est requis (https://git-scm.com/downloads)."
command -v docker >/dev/null 2>&1 || fail "Docker est requis (https://docs.docker.com/get-docker/)."
if docker compose version >/dev/null 2>&1; then
    COMPOSE="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE="docker-compose"
else
    fail "Docker Compose est requis (inclus dans Docker Desktop, ou 'docker-compose' standalone)."
fi

if [ -d "$DEST/.git" ]; then
    info "Dépôt déjà cloné dans $DEST — mise à jour..."
    git -C "$DEST" pull --ff-only
elif [ -e "$DEST" ]; then
    fail "$DEST existe déjà et n'est pas un dépôt git de Synopsis. Supprime-le, ou lance : SYNOPSIS_DIR=autre-dossier bash install.sh"
else
    info "Clonage dans $DEST..."
    git clone --depth 1 "$REPO_URL" "$DEST"
fi

cd "$DEST"
info "Construction et démarrage (peut prendre une minute la première fois)..."
$COMPOSE up -d --build

info "Attente que le service réponde sur le port $PORT..."
for _ in $(seq 1 30); do
    if curl -fsS "http://localhost:$PORT/sante" >/dev/null 2>&1; then
        ok "Synopsis tourne : http://localhost:$PORT"
        exit 0
    fi
    sleep 1
done

fail "Le service ne répond pas après 30s — vérifie les logs : (cd $DEST && $COMPOSE logs)"
