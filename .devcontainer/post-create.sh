#!/usr/bin/env bash
# Runs once, when the container is created. Does the three things an attendee
# would otherwise do by hand: install dependencies, create .env, and say
# plainly whether this container can hear anything.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> Installing dependencies (uv sync)"
uv sync

if [ ! -f .env ]; then
    cp .env.example .env
    echo "==> Created .env from .env.example"
fi

# If the key arrived as a Codespaces secret or a host environment variable, put
# it in .env too -- only when .env has an empty placeholder, so a key already
# typed in there is never overwritten.
if [ -n "${DEEPGRAM_API_KEY:-}" ]; then
    python3 - <<'PY'
import os
import pathlib

env = pathlib.Path(".env")
lines = env.read_text().splitlines(keepends=True)
key = os.environ["DEEPGRAM_API_KEY"]

for i, line in enumerate(lines):
    if line.strip() == "DEEPGRAM_API_KEY=":
        lines[i] = f"DEEPGRAM_API_KEY={key}\n"
        env.write_text("".join(lines))
        print("==> Wrote DEEPGRAM_API_KEY into .env")
        break
PY
fi

echo
if [ -e /dev/snd ] || [ -n "${PULSE_SERVER:-}" ]; then
    echo "Audio: this container has been given access to host audio devices."
    echo "       Run the Step 1 check to confirm both directions work:"
    echo
    echo "         uv run steps/01-setup/main.py"
else
    echo "Audio: this container has NO microphone or speaker."
    echo
    echo "       Steps 3-8 stream live audio, so they need real hardware. What"
    echo "       works here: reading the labs, editing and linting every step,"
    echo "       Step 2's WebSocket handshake, and Step 8's function logic."
    echo
    echo "       To get audio, either run the workshop on your own machine with"
    echo "       uv, or share your host's audio devices with the container --"
    echo "       .devcontainer/README.md explains both."
fi

echo
echo "Start with steps/00-overview/LAB.md. Everything else is installed."
