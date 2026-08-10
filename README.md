# Deepgram Voice Agent Workshop — Python Edition

Build a real-time voice agent in Python, one runnable step at a time. You speak, it listens on Flux, thinks with an LLM, answers in a natural voice, stops when you interrupt it, and calls your code when it needs something it can't know.

Every step is a complete, working program that opens a browser tab and talks to you. The agent is entirely Python — the browser is only the microphone and the speaker.

Start at Step 1 or drop in at Step 5; each folder already contains everything the previous steps built.

**Not a developer, or on a locked-down laptop, Chromebook, or tablet?** [README_EASY_MODE.md](README_EASY_MODE.md) runs the same workshop entirely in the browser through the [Deepgram Playground](https://playground.deepgram.com/voice-agent) — no install, no terminal. Its labs map one to one onto the steps below, so a mixed room stays in sync.

## Prerequisites

| You need | Why you need it |
|---|---|
| [uv](https://docs.astral.sh/uv/getting-started/installation/) | The only thing to install. It fetches Python 3.13 and every dependency itself, so you don't need Python already. |
| A free [Deepgram API key](https://console.deepgram.com/signup?jump=keys) | Signup takes a minute, and the free credit covers this workshop with room to spare. |
| A current browser | Chrome, Firefox, or Safari. The browser is the microphone and the speaker — it needs `getUserMedia` and `AudioWorklet`. |
| Wired headphones | Your browser cancels most of the echo from your speakers, but not all of it on every browser, and Step 5 is where the difference shows. |
| A terminal | macOS, Linux, Windows, and WSL all work — under WSL the audio is Windows' problem, not yours. |

Being comfortable with Python helps. An audio or machine-learning background doesn't.

**Don't want to install anything?** [.devcontainer/README.md](.devcontainer/README.md) runs the whole workshop in a container — GitHub Codespaces needs nothing local at all, and VS Code Dev Containers needs only Docker. Both arrive with `uv sync` already run and `.env` already created, so you paste your key and start at Step 1. Your microphone and browser stay on your machine either way; the only thing a container takes away is the `--local` flag below.

## Setup

Once you have uv and a key:

```bash
uv sync
cp .env.example .env      # then paste your key into .env
uv run steps/01-setup/main.py
```

One virtual environment serves every step. You run `uv sync` once.

That last command checks your key in the terminal, then opens a browser page that checks the rest: microphone permission, the audio APIs, input level, and output. Better here than mid-conversation later.

Every step from Step 2 on serves a page at `http://127.0.0.1:8000` and opens it for you. **It has to be `127.0.0.1`** — browsers only grant microphone access on a secure context, and a LAN address is not one.

### Running in another region

Deepgram serves the same APIs from more than one place. Global is the default; the EU and AU endpoints process audio inside those geographies. Pick one in `.env`:

```bash
DEEPGRAM_REGION=eu        # global (default), eu, or au
```

That is the whole change. Your key works in every region, no step's code names one, and every step reads the same `.env` — so one line moves Steps 1 through 8 together.

Step 1 then starts the agent against whichever endpoint you picked and reports whether that endpoint serves all three models. Model availability differs by region and moves over time, so that — not the key, and not whether the host answers — is the question worth asking before a room of people hits Step 2.

[web/region.py](web/region.py) has the details, and the same mechanism points the workshop at a Deepgram Dedicated or self-hosted deployment.

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
| [0 — Overview](steps/00-overview/LAB.md) | *(read only)* The parts of a voice agent | — | 10 min |
| [1 — Setup](steps/01-setup/LAB.md) | Verify key, browser, and microphone | `uv run steps/01-setup/main.py` | 15 min |
| [2 — Connect](steps/02-connect/LAB.md) | The WebSocket and settings handshake | `uv run steps/02-connect/main.py` | 20 min |
| [3 — Hear the agent](steps/03-hear-the-agent/LAB.md) | Playback — the greeting plays | `uv run steps/03-hear-the-agent/main.py` | 25 min |
| [4 — Talk to the agent](steps/04-talk-to-the-agent/LAB.md) | Microphone input — a real conversation | `uv run steps/04-talk-to-the-agent/main.py` | 30 min |
| [5 — Barge-in](steps/05-barge-in/LAB.md) | Interrupting the agent mid-sentence | `uv run steps/05-barge-in/main.py` | 25 min |
| [6 — Make it yours](steps/06-make-it-yours/LAB.md) | Prompt, persona, voice, model | `uv run steps/06-make-it-yours/main.py` | 20 min |
| [6b — Bring your own LLM](steps/06b-bring-your-own-llm/LAB.md) *(optional)* | The brain on Amazon Bedrock, in your AWS account | `uv run steps/06b-bring-your-own-llm/main.py` | 15 min |
| [7 — Function calling](steps/07-function-calling/LAB.md) | The agent runs your Python | `uv run steps/07-function-calling/main.py` | 35 min |
| [8 — Optimization](steps/08-optimize/LAB.md) | End-of-turn thresholds and latency | `uv run steps/08-optimize/main.py` | 20 min |
| [Finished](steps/99-final/README.md) | The complete reference implementation | `uv run steps/99-final/main.py` | — |

Running behind? Steps 1–5 are the core — finish those and you have a working voice agent. Step 8 is dials rather than code and makes the natural take-home. And because every folder is complete, skipping ahead costs you the typing, not the workshop.

Step 6b is a detour, not a link in the chain: it's the only step that needs a credential beyond your Deepgram key — AWS access with Bedrock model access granted, which usually takes longer to obtain than the step takes to do. Skip it and Step 7 continues from Step 6 exactly as it would have.

Each lab has **Check yourself** questions to test your understanding as you go, and **⏸ Pause** markers where a live workshop regroups.

## What you'll learn

- Configuring speech-to-text, an LLM, and text-to-speech through a single WebSocket
- Why Flux does turn detection server-side, and what that removes from your client
- Streaming microphone audio without blocking the thread that plays the reply
- Clearing queued playback the instant a user interrupts — the difference between a demo and something people will use
- Wiring client-side function calls into a live conversation
- Trading turn-detection latency against accuracy, and measuring it honestly

The audio plumbing itself lives in [web/](web/) — a small FastAPI bridge and two AudioWorklets that every step shares and you read rather than write. [web/README.md](web/README.md) explains what it does and the three things about it that are easy to get wrong.

## Getting help

- [Deepgram Voice Agent docs](https://developers.deepgram.com/docs/voice-agent)
- [Flux docs](https://developers.deepgram.com/docs/flux)
- [GitHub Discussions](https://github.com/orgs/deepgram/discussions)
- [Discord](https://discord.gg/xWRaCDBtW4)

## Running this workshop yourself

[FACILITATOR.md](FACILITATOR.md) has the run of show with timings and sync points, a pre-event setup email to send a week ahead, the five environment failures you'll actually hit, an answer key for the Check-yourself questions, and guidance on managing pace spread in a room.

[slides/deepgram-voice-agent-workshop.pptx](slides/deepgram-voice-agent-workshop.pptx) is the projection deck that goes with it, a visual aid to hold the room on the current step, not a talk to deliver.

`scripts/verify_steps.py` checks that every step compiles, lints, and leaks no unfinished TODO markers into the next folder's answer key:

```bash
uv run scripts/verify_steps.py
```

Run it after editing any step, or anything under `web/` — ruff covers both. Nine near-identical copies of `main.py` drift quietly, and drift between a step and its answer key is the failure mode that shows up live.
