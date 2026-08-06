# Deepgram Voice Agent Workshop — Python Edition

Build a real-time voice agent in Python, one runnable step at a time. You speak, it listens on Flux, thinks with an LLM, answers in a natural voice, stops when you interrupt it, and calls your code when it needs something it can't know.

Every step is a complete, working program that opens a browser tab and talks to you. The agent is entirely Python — the browser is only the microphone and the speaker.

Start at Step 1 or drop in at Step 5; each folder already contains everything the previous steps built.

## Setup

You need [uv](https://docs.astral.sh/uv/getting-started/installation/) and a free [Deepgram API key](https://console.deepgram.com/signup?jump=keys).

```bash
uv sync
cp .env.example .env      # then paste your key into .env
uv run steps/01-setup/main.py
```

One virtual environment serves every step. You run `uv sync` once.

That last command checks your key in the terminal, then opens a browser page that checks the rest: microphone permission, the audio APIs, input level, and output. Better here than mid-conversation later.

Every step from Step 2 on serves a page at `http://127.0.0.1:8000` and opens it for you. **It has to be `127.0.0.1`** — browsers only grant microphone access on a secure context, and a LAN address is not one.

**Headphones still help.** Your browser cancels most of the echo from your speakers, but not all of it on every browser, and Step 5 is where the difference shows.

### Prefer the terminal?

Add `--local` to any step and it uses your system microphone and speaker through PortAudio instead, with no browser involved:

```bash
uv run steps/99-final/main.py --local
```

Same agent code either way — see [web/README.md](web/README.md) for what changes underneath.

## The steps

Each folder holds the finished state of the step before it. Open `LAB.md` for instructions, work the `TODO (Step N.x)` blocks in `main.py`, and check the next folder if you get stuck — it's the answer key.

| Step | You build | Run it | Time |
|---|---|---|---|
| [0 — Overview](steps/00-overview/LAB.md) | *(read only)* What a voice agent is made of | — | 10 min |
| [1 — Setup](steps/01-setup/LAB.md) | Verify key, browser, and microphone | `uv run steps/01-setup/main.py` | 15 min |
| [2 — Connect](steps/02-connect/LAB.md) | The WebSocket and settings handshake | `uv run steps/02-connect/main.py` | 20 min |
| [3 — Hear the agent](steps/03-hear-the-agent/LAB.md) | Playback — the greeting plays | `uv run steps/03-hear-the-agent/main.py` | 25 min |
| [4 — Talk to the agent](steps/04-talk-to-the-agent/LAB.md) | Microphone input — a real conversation | `uv run steps/04-talk-to-the-agent/main.py` | 30 min |
| [5 — Barge-in](steps/05-barge-in/LAB.md) | Interrupting the agent mid-sentence | `uv run steps/05-barge-in/main.py` | 25 min |
| [6 — Tune turn detection](steps/06-tune-turns/LAB.md) | End-of-turn thresholds and latency | `uv run steps/06-tune-turns/main.py` | 20 min |
| [7 — Make it yours](steps/07-make-it-yours/LAB.md) | Prompt, persona, voice, model | `uv run steps/07-make-it-yours/main.py` | 20 min |
| [8 — Function calling](steps/08-function-calling/LAB.md) | The agent runs your Python | `uv run steps/08-function-calling/main.py` | 35 min |
| [Finished](steps/99-final/README.md) | The complete reference implementation | `uv run steps/99-final/main.py` | — |

Running behind? Steps 1–5 are the core — finish those and you have a working voice agent. Steps 6–8 stand alone well enough to work through afterward. And because every folder is complete, skipping ahead costs you the typing, not the workshop.

Each lab has **Check yourself** questions to test your understanding as you go, and **⏸ Pause** markers where a live workshop regroups.

## What you'll learn

- Configuring speech-to-text, an LLM, and text-to-speech through a single WebSocket
- Why Flux does turn detection server-side, and what that removes from your client
- Streaming microphone audio without blocking the thread that plays the reply
- Clearing queued playback the instant a user interrupts — the difference between a demo and something people will use
- Trading turn-detection latency against accuracy, and measuring it honestly
- Wiring client-side function calls into a live conversation

The audio plumbing itself lives in [web/](web/) — a small FastAPI bridge and two AudioWorklets, shared by every step and read rather than written. [web/README.md](web/README.md) explains what it does and the three things about it that are easy to get wrong.

## Getting help

- [Deepgram Voice Agent docs](https://developers.deepgram.com/docs/voice-agent)
- [Flux docs](https://developers.deepgram.com/docs/flux)
- [GitHub Discussions](https://github.com/orgs/deepgram/discussions)
- [Discord](https://discord.gg/xWRaCDBtW4)

## Running this workshop yourself

[FACILITATOR.md](FACILITATOR.md) has the run of show with timings and sync points, a pre-event setup email to send a week ahead, the five environment failures you'll actually hit, an answer key for the Check-yourself questions, and guidance on managing pace spread in a room.

`scripts/verify_steps.py` checks that every step compiles, lints, and leaks no unfinished TODO markers into the next folder's answer key:

```bash
uv run scripts/verify_steps.py
```

Run it after editing any step, or anything under `web/` — ruff covers both. Nine near-identical copies of `main.py` drift quietly, and drift between a step and its answer key is the failure mode that shows up live.
