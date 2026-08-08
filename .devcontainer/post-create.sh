#!/usr/bin/env bash
#
# Runs once, after the container is created and the workspace is mounted.
# Everything here is what README.md's Setup section asks an attendee to do by
# hand, done for them: the environment file, and one `uv sync`.
set -euo pipefail

cd "$(dirname "$0")/.."

# A freshly created named volume is owned by root, and .venv is one. uv would
# otherwise fail on its first write with a permission error that reads like a
# broken image rather than a one-line fix.
if [ ! -w .venv ]; then
  sudo chown "$(id -u):$(id -g)" .venv
fi

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example."
fi

uv sync

echo
if [ -n "${DEEPGRAM_API_KEY:-}" ]; then
  # A Codespaces secret, or a variable passed through from the host. Steps call
  # load_dotenv(), which never overwrites a variable that is already set, so
  # this wins over .env without anything being written to disk.
  echo "DEEPGRAM_API_KEY is set in the environment -- no need to edit .env."
else
  echo "Next: paste your Deepgram API key into .env, then run"
  echo "  uv run steps/01-setup/main.py"
fi
