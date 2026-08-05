# Deepgram Voice Agent Workshop — Python Edition

[![Discord](https://img.shields.io/discord/1108042150941294664)](https://discord.gg/xWRaCDBtW4)

Build a real-time voice agent in Python, one runnable step at a time. You speak, it listens on Flux, thinks with an LLM, answers in a natural voice, stops when you interrupt it, and calls your code when it needs something it can't know.

Every step is a complete, working program. Start at Step 1 or drop in at Step 5 — each folder already contains everything the previous steps built.

## Setup

You need [uv](https://docs.astral.sh/uv/getting-started/installation/) and a free [Deepgram API key](https://console.deepgram.com/signup?jump=keys).

```bash
uv sync
cp .env.example .env      # then paste your key into .env
uv run steps/01-setup/main.py
```

One virtual environment serves every step. You run `uv sync` once.

That last command checks your key, your audio devices, and your microphone before any of it matters. On macOS it also triggers the microphone permission prompt — much better here than mid-conversation later.

**Headphones are strongly recommended.** Without them your speaker feeds your microphone and the agent interrupts itself, which is confusing in Step 4 and actively misleading in Step 5.

## The steps

Each folder holds the finished state of the step before it. Open `LAB.md` for instructions, work the `TODO (Step N.x)` blocks in `main.py`, and check the next folder if you get stuck — it's the answer key.

| Step | You build | Run it | Time |
|---|---|---|---|
| [0 — Overview](steps/00-overview/LAB.md) | *(read only)* What a voice agent is made of | — | 10 min |
| [1 — Setup](steps/01-setup/LAB.md) | Verify key, devices, and microphone | `uv run steps/01-setup/main.py` | 15 min |
| [2 — Connect](steps/02-connect/LAB.md) | The WebSocket and settings handshake | `uv run steps/02-connect/main.py` | 20 min |
| [3 — Hear the agent](steps/03-hear-the-agent/LAB.md) | Speaker output — the greeting plays | `uv run steps/03-hear-the-agent/main.py` | 25 min |
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
- Streaming microphone audio without blocking PortAudio's realtime thread
- Clearing queued playback the instant a user interrupts — the difference between a demo and something people will use
- Trading turn-detection latency against accuracy, and measuring it honestly
- Wiring client-side function calls into a live conversation

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

Run it after editing any step. Nine near-identical copies of `main.py` drift quietly, and drift between a step and its answer key is the failure mode that shows up live.
