# Facilitator guide

Everything you need to run this workshop in a room. Attendees don't need this file.

## At a glance

| | |
|---|---|
| **Format** | Hands-on, attendees code on their own machines |
| **Full run** | ~3 hours (Steps 0 to 8) |
| **Short run** | ~90 minutes (Steps 0 to 5), and it still ends with a working voice agent |
| **Staffing** | One instructor, plus one floating helper per ~15 attendees |
| **Prerequisites** | Comfortable with Python is a plus, but not a requirement; no audio or ML background needed |
| **Cost per attendee** | Well under $1. New accounts get $200 in credit |

The single biggest predictor of whether this workshop goes well is how many people arrive with a working environment. Send the pre-event email.

## Send this a week ahead

> **Before the workshop: 10 minutes of setup**
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

**Only if you're running the optional Step 6b**, add a fifth item asking people to enable Bedrock model access for `zai.glm-4.7-flash` in one region at [Bedrock → Model access](https://console.aws.amazon.com/bedrock/home#/modelaccess), and to have an access key ready. Send that version *earlier* than a week out. Access is per model and per region, and the approval isn't always instant. Leave it out of the default email; it's noise for a room that isn't doing the step.

## Running it in another region

Deepgram's global endpoint is the default and is what the pre-event email above assumes. If the room needs audio processed inside the EU or Australia, set one line in `.env` and hand out the repository as usual:

```bash
DEEPGRAM_REGION=eu        # global (default), eu, or au
```

Nothing in `steps/` names a region. Every step reads the same `.env`, so this moves all of them at once.

You don't have to test the region yourself. Step 1 opens the same WebSocket Step 2 opens, with the same three models, and reports whether the server accepted them:

```
[  OK  ] Region: eu (wss://api.eu.deepgram.com/v1/agent/converse)
[  OK  ] Agent started (flux-general-en + gpt-4o-mini + flux-alexis-en)
```

That is the check that matters regionally. Model availability is per-region and moves over time. A key that works and an endpoint that answers still don't tell you a model is served there. If one isn't, the agent names it in an `Error` frame and Step 1 prints it, along with the two ways out: `DEEPGRAM_REGION=global`, or swap the model the error names in every step.

**As of August 2026, `au` needs one change.** Flux TTS is not served there yet, so `flux-alexis-en` is refused. Flux STT and the LLM are fine. Set `speak` to `aura-2-thalia-en` in every step's `SETTINGS` and the workshop runs unchanged; Step 6 teaches changing the voice anyway, so it costs the room nothing. `eu` and `global` both run the workshop as shipped. Step 1 tells each attendee this directly, so you'll find out even if this note goes stale.

Add the `DEEPGRAM_REGION` line to the pre-event email if attendees will clone the repo themselves. `.env.example` documents it, but people paste their key and stop reading.

## The slide deck

[slides/deepgram-voice-agent-workshop.pptx](slides/deepgram-voice-agent-workshop.pptx) is a
PowerPoint-compatible projection deck that mirrors the run of show below.

**The slides are a visual aid for the room, not a talk.** You do not need to read through them
or present each one before the workshop starts. Most of them exist to be left on screen while
people work, so anyone who looks up can see which step the room is on, the command to run, and
what has to be true before we move. Only the six Step 0 slides are presented, and that block is
capped at ten minutes.

How the deck is laid out:

| Slides | What they are |
|---|---|
| 1 to 6 | Title, what they'll build, prerequisites, the two tracks, and this run of show |
| 7 to 13 | Step 0. The only block you actually present |
| 14 to 23 | Steps 1 to 5, one gate slide each, plus the break |
| 24 to 29 | Steps 6 to 8 |
| 30 to 33 | Wrap, where to go next, links |
| 34 to 37 | Appendix: the five failures, the check-yourself answers, and regions. Not part of the run; jump to them when the room needs them |

Each step gate slide carries the step number, its clock time, its duration, and the matching Easy
Mode lab, so a mixed room can read its position off the screen without asking. The amber **pause**
marker on a slide is the same sync point marked in that step's `LAB.md`, and that is the one thing on
the slide you should say out loud.

Every slide has speaker notes with the things worth saying, the failures to watch for, and the
check-yourself answer for that step. They are for you during the session; they are not a script,
and nothing in them needs covering up front.

Slide 33 is sized to hold QR codes and doesn't ship with them. Generate six from the links table
at the end of this file and drop them in if you're presenting to a conference floor, where nobody
will type a URL.

The deck is generated from a script rather than hand-edited. If you change a step's timing or its
sync point here, change it on that step's slide too.

## Run of show

Times assume a 3-hour slot with one break. The **⏸** rows are the sync points marked in each `LAB.md`. Hold the room at these.

| Time | Step | What happens | Watch for |
|---|---|---|---|
| 0:00 | **0: Overview** | You present. Three models, what the API orchestrates, what Flux changes | Keep it to 10 min; they came to code |
| 0:10 | **1: Setup** | Everyone runs the checker | **⏸** Nobody proceeds without a green key line and a green `Agent started` |
| 0:25 | **2: Connect** | Handshake | **⏸** Everyone sees `>> Settings applied` |
| 0:45 | **3: Hear the agent** | Speaker output | **⏸** Everyone *hears* the greeting |
| 1:10 | **4: Talk to the agent** | Microphone, full loop | **⏸** Everyone holds a conversation. High point, so let it breathe |
| 1:40 | - | **Break, 10 min** | Use it to unstick stragglers |
| 1:50 | **5: Barge-in** | Interruption | **⏸** Everyone experiences the bug *before* fixing it |
| 2:15 | **6: Make it yours** | Persona and voice | **⏸** Go around the room and demo a few |
| 2:35 | **7: Function calling** | Tools | **⏸** Sketch a function for their own use case first |
| 3:05 | **8: Optimization** | EOT thresholds, latency | Pace-recovery step. Stragglers catch up here, and it sheds time cleanly |
| 3:20 | **Wrap** | `steps/99-final/README.md`, Q&A | Point at Discord and the docs |

**Step 6b is not in the run of show, and that's deliberate.** It moves the LLM to Amazon Bedrock in the attendee's own AWS account, which needs Bedrock model access granted per model *and* per region, which for a fresh account is a day or two of calendar time, not a day or two of work. Mention it in one sentence when you finish Step 6, as a take-home, and move on.

Run it live only if you know the room already has AWS: an enterprise team, an AWS-hosted event. In that case it slots in after Step 6 and costs about 15 minutes, and you should say so in the pre-event email so people arrive with model access approved. Everything it teaches (`think.endpoint`, brokered vs bring-your-own providers) is in its `LAB.md`, so it reads fine unattended.

**If you're running long.** Cut Step 8 and Step 7's exercises. Both work fine as take-home, and Step 8 is deliberately last so it can go. Never cut Step 5; it's the step people remember.

**If you're running short.** Step 8's "Going further" (`eager_eot_threshold`) and Step 7's second function absorb time well.

## The five failures you will actually hit

**1. Microphone permission.** The prompt appears during Step 1 and people click past it. Fix: the icon at the left of the address bar, allow, press the button again. On macOS also check **System Settings → Privacy & Security → Microphone** and confirm the *browser* is enabled. Note it is the browser now, not the terminal.

**2. The page is open on the wrong address.** `getUserMedia` and `AudioWorklet` need a secure context, which browsers grant to `localhost` and nothing else, so a LAN address makes the audio API silently vanish. Symptom: the Connect button stays disabled with a red box above it. Fix: use the `http://127.0.0.1:8000` the terminal printed. This replaces WSL-has-no-audio as the environment failure to watch for; WSL now works, because the audio is Windows' problem.

**3. Bluetooth headsets.** Activating the microphone flips many headsets into a low-quality mono profile, and some then fail to open at all. Reconnect, or switch to wired. This is why the pre-event email asks for wired.

**4. The agent talks to itself.** Laptop speakers feeding the laptop microphone, past the echo canceller. Much rarer than it used to be and no longer universal, which makes it *more* confusing when it happens to one person in the room. Headphones, or turn the volume down. Step 1's check reports whether the browser actually granted echo cancellation, which is worth reading when someone hits this.

**5. A truncated API key.** Copy-paste drops characters or adds a space. Step 1 makes a real authenticated call rather than checking the string is non-empty, so this surfaces immediately with `Deepgram rejected the key`.

**And one that is not an environment failure at all:** `The agent refused these settings`. The machine is fine. A model isn't available where that person is connecting. Step 1 prints which. Same fix for the whole room, since they share a `.env` layout: `DEEPGRAM_REGION=global`, or change the named model everywhere.

**And a sixth, only if you're running Step 6b: Bedrock model access.** Not on the main line, but by far the longest to fix if it comes up, because you can't fix it in the room. Access is granted per model *and* per region, and some families (Anthropic's among them) need a one-time use case form that isn't instant. Two cheaper mistakes shadow it and are worth ruling out first: a region mismatch between the credentials and the endpoint URL, and an IAM user holding `bedrock:InvokeModel` but not `bedrock:InvokeModelWithResponseStream`. The agent streams, so the non-streaming permission alone isn't enough. Anyone arriving from the Pipecat edition will also reach for `AWS_BEARER_TOKEN_BEDROCK`, which does nothing here.

## Managing pace spread

The step folders exist for exactly this problem. Someone stuck on Step 3 at the 1:40 mark should **skip to `steps/05-barge-in/`** and keep going. That folder already contains a complete working Steps 1 to 4. They lose the typing, not the workshop.

Say this out loud at the first sync point so people know it's allowed. Otherwise they'll quietly fall behind and disengage.

The answer key for any step is the next folder's `main.py`. When someone is stuck on a detail and the room is moving, point them there rather than debugging live.

## Check-yourself answers

The `LAB.md` files pose these; here are the answers, for when you ask the room.

**Step 0.** STT, LLM, TTS; the LLM holds the conversation history. · Turn-taking, provider handoffs, buffering, interruption signalling. · Turn detection happens inside the Flux model, server-side; the client is still responsible for clearing queued playback on barge-in. · The next folder.

**Step 1.** One. Deepgram brokers the OpenAI call, so your Deepgram key covers the LLM.

**Step 2.** `listen` configures speech-to-text; the LLM is named under `think`. · The agent discards any media that arrives before the handshake completes, so audio sent early is silently lost.

**Step 3.** The greeting starts arriving within milliseconds of `SettingsApplied`, and audio with nowhere to go is audio thrown away. The bridge waits for the browser's `start` message before it opens the Deepgram socket for exactly this reason.

**Step 4.** Flux does turn detection inside the model, so there's nothing for client-side VAD to do.

**Step 5.** Because the pump would immediately refill the browser's queue from the Python-side one. Clearing the far queue first and the near queue second means the agent talks over the user a moment later rather than immediately, which is worse, because it looks like it nearly works. (The PortAudio equivalent: `stop()` drains the buffer, playing everything already queued before stopping. `abort()` throws it away.)

**Step 6.** Tell it that it's speaking (no markdown, bullets, or emoji), and tell it to be brief.

**Step 6b.** Deepgram brokers OpenAI, so a model name is the whole configuration. It doesn't broker Bedrock: it makes the call *as you*, which needs credentials to make it with (`provider.credentials`) and an address to make it to (`think.endpoint`).

**Step 7.** Setting `endpoint` moves execution to Deepgram; omitting it keeps the function client-side.

**Step 8.** Raise `eot_threshold`. It demands more confidence before Flux calls the turn over.

## Links for the room

Worth turning into QR codes on a slide, since attendees on a conference floor won't type URLs.

| What | URL |
|---|---|
| Sign up / API key | https://console.deepgram.com/signup?jump=keys |
| Voice Agent docs | https://developers.deepgram.com/docs/voice-agent |
| Flux docs | https://developers.deepgram.com/docs/flux |
| Voice catalogue | https://developers.deepgram.com/docs/tts-models |
| Bedrock model access (Step 6b only) | https://console.aws.amazon.com/bedrock/home#/modelaccess |
| Discord | https://discord.gg/xWRaCDBtW4 |
| GitHub Discussions | https://github.com/orgs/deepgram/discussions |

## After the session

Share the repo link again, point at [steps/99-final/README.md](steps/99-final/README.md) for extension ideas, and invite people into Discord while they still have the agent running.

Worth capturing while it's fresh: which step consumed the most time, how many people finished Step 7, and which environment failures actually occurred. That's what you'll change before the next run.

## Maintaining this repo

```bash
uv run scripts/verify_steps.py
```

Checks that every step compiles, no TODO markers leak into the next folder's answer key, docs are present, and ruff passes. Run it after editing any step. Nine near-identical copies of `main.py` drift quietly.
