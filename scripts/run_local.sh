#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -x .venv/bin/python ]]; then
  echo "Virtual environment not found at .venv/bin/python" >&2
  exit 1
fi

export MUSIC_SERVER_DATA_DIR="${MUSIC_SERVER_DATA_DIR:-$ROOT_DIR/.music-server}"
export MUSIC_SERVER_MUSIC_DIR="${MUSIC_SERVER_MUSIC_DIR:-$HOME/Music}"

exec .venv/bin/python -m music_server.app "$@"
