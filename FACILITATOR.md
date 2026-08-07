# Facilitator guide

Everything you need to run this workshop in a room. Attendees don't need this file.

## At a glance

| | |
|---|---|
| **Format** | Hands-on, attendees code on their own machines |
| **Full run** | ~3 hours (Steps 0–8) |
| **Short run** | ~90 minutes (Steps 0–5) — still ends with a working voice agent |
| **Staffing** | One instructor, plus one floating helper per ~15 attendees |
| **Prerequisites** | Comfortable with Python; no audio or ML background needed |
| **Cost per attendee** | Well under $1. New accounts get $200 in credit |

The single biggest predictor of whether this workshop goes well is how many people arrive with a working environment. Send the pre-event email.

## Send this a week ahead

> **Before the workshop — 10 minutes of setup**
>
> Please do this before you arrive so we can start with the interesting part.
>
> 1. Install [uv](https://docs.astral.sh/uv/getting-started/installation/)
> 2. Sign up at [console.deepgram.com](https://console.deepgram.com/signup?jump=keys) and create an API key (new accounts get $200 free credit)
> 3. Clone the repo and run the setup check:
>    ```bash
>    git clone <REPO_URL> && cd deepgram-workshop-py
>    uv sync
>    cp .env.example .env    # paste your key in
>    uv run steps/01-setup/main.py
>    ```
> 4. **Bring wired headphones.** Your browser cancels most of the echo, but not all of it on every browser. Without headphones the agent can hear itself and interrupt itself, which makes Step 5 confusing.
>
> The setup check finishes in a browser page. Chrome, Firefox, or Safari, reasonably current.
>
> If the check prints anything other than all-OK, reply to this email and we'll sort it out before the day.

## Run of show

Times assume a 3-hour slot with one break. The **⏸** rows are the sync points marked in each `LAB.md` — hold the room at these.

| Time | Step | What happens | Watch for |
|---|---|---|---|
| 0:00 | **0 — Overview** | You present. Three models, what the API orchestrates, what Flux changes | Keep it to 10 min; they came to code |
| 0:10 | **1 — Setup** | Everyone runs the checker | **⏸** Nobody proceeds without a green key line |
| 0:25 | **2 — Connect** | Handshake | **⏸** Everyone sees `>> Settings applied` |
| 0:45 | **3 — Hear the agent** | Speaker output | **⏸** Everyone *hears* the greeting |
| 1:10 | **4 — Talk to the agent** | Microphone, full loop | **⏸** Everyone holds a conversation. High point — let it breathe |
| 1:40 | — | **Break, 10 min** | Use it to unstick stragglers |
| 1:50 | **5 — Barge-in** | Interruption | **⏸** Everyone experiences the bug *before* fixing it |
| 2:15 | **6 — Make it yours** | Persona and voice | **⏸** Go around the room and demo a few |
| 2:35 | **7 — Function calling** | Tools | **⏸** Sketch a function for their own use case first |
| 3:05 | **8 — Optimization** | EOT thresholds, latency | Pace-recovery step. Stragglers catch up here, and it sheds time cleanly |
| 3:20 | **Wrap** | `steps/99-final/README.md`, Q&A | Point at Discord and the docs |

**Running long?** Cut Step 8 and Step 7's exercises — both work fine as take-home, and Step 8 is deliberately last so it can go. Never cut Step 5; it's the step people remember.

**Running short?** Step 8's "Going further" (`eager_eot_threshold`) and Step 7's second function absorb time well.

## The five failures you will actually hit

**1. Microphone permission.** The prompt appears during Step 1 and people click past it. Fix: the icon at the left of the address bar, allow, press the button again. On macOS also check **System Settings → Privacy & Security → Microphone** and confirm the *browser* is enabled — note it is the browser now, not the terminal.

**2. The page is open on the wrong address.** `getUserMedia` and `AudioWorklet` need a secure context, which browsers grant to `localhost` and nothing else — so a LAN address makes the audio API silently vanish. Symptom: the Connect button stays disabled with a red box above it. Fix: use the `http://127.0.0.1:8000` the terminal printed. This replaces WSL-has-no-audio as the environment failure to watch for; WSL now works, because the audio is Windows' problem.

**3. Bluetooth headsets.** Activating the microphone flips many headsets into a low-quality mono profile, and some then fail to open at all. Reconnect, or switch to wired. This is why the pre-event email asks for wired.

**4. The agent talks to itself.** Laptop speakers feeding the laptop microphone, past the echo canceller. Much rarer than it used to be and no longer universal, which makes it *more* confusing when it happens to one person in the room. Headphones, or turn the volume down. Step 1's check reports whether the browser actually granted echo cancellation — worth reading when someone hits this.

**5. A truncated API key.** Copy-paste drops characters or adds a space. Step 1 makes a real authenticated call rather than checking the string is non-empty, so this surfaces immediately with `Deepgram rejected the key`.

## Managing pace spread

The step folders exist for exactly this problem. Someone stuck on Step 3 at the 1:40 mark should **skip to `steps/05-barge-in/`** and keep going — that folder already contains a complete working Steps 1–4. They lose the typing, not the workshop.

Say this out loud at the first sync point so people know it's allowed. Otherwise they'll quietly fall behind and disengage.

The answer key for any step is the next folder's `main.py`. When someone is stuck on a detail and the room is moving, point them there rather than debugging live.

## Check-yourself answers

The `LAB.md` files pose these; here are the answers, for when you ask the room.

**Step 0** — STT, LLM, TTS; the LLM holds the conversation history. · Turn-taking, provider handoffs, buffering, interruption signalling. · Turn detection happens inside the Flux model, server-side; the client is still responsible for clearing queued playback on barge-in. · The next folder.

**Step 1** — One. Deepgram brokers the OpenAI call, so your Deepgram key covers the LLM.

**Step 2** — `listen` configures speech-to-text; the LLM is named under `think`. · The agent discards any media that arrives before the handshake completes, so audio sent early is silently lost.

**Step 3** — The greeting starts arriving within milliseconds of `SettingsApplied`, and audio with nowhere to go is audio thrown away. The bridge waits for the browser's `start` message before it opens the Deepgram socket for exactly this reason.

**Step 4** — Flux does turn detection inside the model, so there's nothing for client-side VAD to do.

**Step 5** — Because the pump would immediately refill the browser's queue from the Python-side one. Clearing the far queue first and the near queue second means the agent talks over the user a moment later rather than immediately — which is worse, because it looks like it nearly works. (The PortAudio equivalent: `stop()` drains the buffer, playing everything already queued before stopping. `abort()` throws it away.)

**Step 6** — Tell it that it's speaking (no markdown, bullets, or emoji), and tell it to be brief.

**Step 7** — Setting `endpoint` moves execution to Deepgram; omitting it keeps the function client-side.

**Step 8** — Raise `eot_threshold`. It demands more confidence before Flux calls the turn over.

## Links for the room

Worth turning into QR codes on a slide — attendees on a conference floor won't type URLs.

| What | URL |
|---|---|
| Sign up / API key | https://console.deepgram.com/signup?jump=keys |
| Voice Agent docs | https://developers.deepgram.com/docs/voice-agent |
| Flux docs | https://developers.deepgram.com/docs/flux |
| Voice catalogue | https://developers.deepgram.com/docs/tts-models |
| Discord | https://discord.gg/xWRaCDBtW4 |
| GitHub Discussions | https://github.com/orgs/deepgram/discussions |

## After the session

Share the repo link again, point at [steps/99-final/README.md](steps/99-final/README.md) for extension ideas, and invite people into Discord while they still have the agent running.

Worth capturing while it's fresh: which step consumed the most time, how many people finished Step 7, and which environment failures actually occurred. That's what you'll change before the next run.

## Maintaining this repo

```bash
uv run scripts/verify_steps.py
```

Checks that every step compiles, no TODO markers leak into the next folder's answer key, docs are present, and ruff passes. Run it after editing any step — nine near-identical copies of `main.py` drift quietly.
