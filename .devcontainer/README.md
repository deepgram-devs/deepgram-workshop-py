# .devcontainer/ — the workshop in a container

Runs the whole workshop with nothing installed on the machine but an editor: no
Python, no uv, no key management beyond one paste. Two ways in.

**GitHub Codespaces** — from the repository page, *Code → Codespaces → Create
codespace on main*. Nothing local at all.

**VS Code Dev Containers** — install the
[Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers),
open this folder, and accept *Reopen in Container*. Docker has to be running.

Either way the container builds, `uv sync` runs, and `.env` is created from
`.env.example`. Paste your key into `.env` and start at Step 1 exactly as
[README.md](../README.md) describes:

```bash
uv run steps/01-setup/main.py
```

In a Codespace you can skip the paste: set `DEEPGRAM_API_KEY` as a
[Codespaces secret](https://github.com/settings/codespaces) and it arrives as an
environment variable. Every step calls `load_dotenv()`, which does not overwrite
a variable that is already set, so the secret wins and `.env` can stay empty.

## What is in here

| File | What it is |
|---|---|
| `devcontainer.json` | The container's contract: image, port 8000, the `.venv` volume, VS Code extensions and settings. |
| `Dockerfile` | Microsoft's Python 3.13 dev container image, plus the `uv` binary copied out of Astral's image. |
| `post-create.sh` | Runs once after create: fixes `.venv` ownership, seeds `.env`, runs `uv sync`. |

## The microphone still lives outside

This is the one thing worth reading before Step 1. The container has no audio
hardware and does not need any — the browser is the microphone and the speaker,
and the browser is on your machine, not in here. Port 8000 is forwarded, and the
step's own `webbrowser.open` (plus VS Code's auto-forward) puts the page in front
of you at a URL your browser already trusts:

| | The page opens at | Secure context |
|---|---|---|
| Dev Containers | `http://127.0.0.1:8000` on the host | yes — browsers trust `localhost` |
| Codespaces | `https://…-8000.app.github.dev` | yes — it is HTTPS |

Both satisfy the rule [web/README.md](../web/README.md) explains: `getUserMedia`
and `AudioWorklet` only exist in a secure context. Nothing else about the forward
matters, which is why steps keep binding to `127.0.0.1` in here and no code
changes for containers.

If the page opens twice, the auto-forward and the step both got there. Add
`--no-open` and let the forward do it:

```bash
uv run steps/04-talk-to-the-agent/main.py --no-open
```

## `--local` does not work in here

`--local` is the PortAudio path — the system microphone and speaker, no browser.
There is no system microphone in a container, so this is the one flag in the
workshop that a container takes away. Every step's default path works, and it is
the path the workshop is written around; if you specifically want to exercise
PortAudio, run that step on the host instead.

## Rebuilding

`uv sync` runs on create, so a dependency change needs *Dev Containers: Rebuild
Container* or a manual `uv sync`. The `.venv` volume outlives a rebuild by
design, and `uv sync` reconciles it either way. To throw it away entirely:

```bash
docker volume rm deepgram-workshop-py-venv
```
