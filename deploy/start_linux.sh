#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${TECHNEXUS_PORT:-8010}"
HOST="${TECHNEXUS_HOST:-127.0.0.1}"

cd "$APP_DIR"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

exec python technexus_app/app.py --host "$HOST" --port "$PORT" --no-browser
