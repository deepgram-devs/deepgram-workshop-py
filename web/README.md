# web/ — the browser bridge

Everything in this folder is shared by every step, and no step edits it. It is the audio layer: a local web server, one WebSocket to a browser tab, and the threads that keep a blocking Deepgram socket from stalling an asyncio event loop.

The point of it existing as a folder rather than as part of each step is the boundary. `steps/NN/main.py` describes an agent and reacts to what it says. This describes how sound gets in and out. Swapping this for a Twilio media stream is a real project; swapping it should not require touching a single line of agent code.

## Why the browser

The audio device layer used to live in each step, on top of `sounddevice` and PortAudio. That works, and it is still here behind `--local`, but it costs more than it looks:

| | Browser | PortAudio (`--local`) |
|---|---|---|
| Install | nothing | PortAudio, plus ALSA/PulseAudio on Linux |
| WSL | works — the audio is Windows' problem | needs an `~/.asoundrc` bridge |
| Permissions | one prompt, in the page | OS-level, per terminal application |
| Device selection | the browser's, already familiar | your OS default, invisible until wrong |
| Resampling | free | your problem |
| **Echo cancellation** | **yes** | **no** |

That last row is the one that changes the workshop. Without echo cancellation the agent hears itself through your speakers and interrupts itself, which looks exactly like a broken barge-in implementation and costs people twenty minutes in Step 5.

## Running it

```bash
uv run steps/99-final/main.py                 # opens http://127.0.0.1:8000
uv run steps/99-final/main.py --port 8001     # when 8000 is taken
uv run steps/99-final/main.py --no-open       # print the URL, don't open a browser
uv run steps/99-final/main.py --local         # system mic and speaker, no browser
```

**It binds to `127.0.0.1`, and that is not just a default.** `getUserMedia` and `AudioWorklet` require a *secure context*. Browsers grant that to `localhost` and to HTTPS, and to nothing else — so serving this on a LAN address makes `ctx.audioWorklet` silently `undefined` rather than throwing anything you could search for. If you need it on another machine, put it behind an HTTPS tunnel rather than binding `0.0.0.0`.

## The pieces

| File | What it is |
|---|---|
| `bridge.py` | `run()` and `run_check()`. The FastAPI app, the `/ws` route, the static mount, argument parsing, and the `--local` path. |
| `session.py` | `AgentSession` — one Deepgram connection and its three threads. `AgentHandle` — the `agent` object steps are handed. |
| `region.py` | Turns `DEEPGRAM_REGION` into the endpoint the SDK connects to. One line in `.env` moves every step. |
| `audio.py` | `BrowserPlayer` and `LocalPlayer` behind one two-method interface, plus `Outbox`, the queue behind the browser one. |
| `static/worklets.js` | `CaptureProcessor` and `PlaybackProcessor`. The only code here that runs on an audio thread. |
| `static/app.js` | The page: WebSocket wiring, `AudioContext` lifecycle, DOM. |
| `static/check.html`, `check.js` | Step 1's setup check. |

## Where it connects

Every Deepgram connection in this repo is opened through `region.deepgram_client()`, which reads `DEEPGRAM_REGION` from `.env` — `global` (the default), `eu`, or `au`. Nothing in `steps/` names a region, so a facilitator running in Frankfurt or Sydney edits one line and hands out the same repository.

The v7 SDK takes no `base_url`; endpoints are described by a `DeepgramClientEnvironment` with one field per protocol and service. `region.py` builds that, which is also how you point this at a Deepgram Dedicated or self-hosted deployment — same four fields, your hostname.

One asymmetry worth knowing: the Management API (`/v1/projects`, the call Step 1 makes to prove your key works) is global only. `region.management_client()` exists to keep that deliberate.

## The wire protocol

One WebSocket at `/ws`. Binary frames are PCM, in both directions. Text frames are JSON.

| Direction | Frame | Meaning |
|---|---|---|
| → server | binary | microphone PCM, one 80 ms chunk |
| → server | `{"type":"start"}` | my speaker is live; connect to Deepgram |
| → server | `{"type":"stop"}` | hang up |
| → browser | binary | Flux TTS audio |
| → browser | `{"type":"ready","capture":bool}` | settings applied; capture if `capture` |
| → browser | `{"type":"clear"}` | barge-in: flush playback |
| → browser | `{"type":"transcript","role":…,"content":…}` | from `ConversationText` |
| → browser | `{"type":"event","name":…}` | thinking / started speaking / audio done |
| → browser | `{"type":"status"｜"latency"｜"error"｜"warning"}` | interface chrome |

The audio format is served separately at `GET /api/audio`, read from the step's `SETTINGS`. The page has to ask for it over HTTP rather than wait for it on the socket, because an `AudioContext`'s sample rate is fixed when it is constructed and construction has to happen inside the click handler that unlocks it.

Microphone level never crosses the wire. The capture worklet computes it and drives the meter locally.

## Three things that are easy to get wrong

**The sender thread.** No coroutine ever calls `send_media` directly. `websockets`' `send()` joins its receive thread with `close_timeout` — ten seconds by default, and the SDK does not override it — as soon as a connection starts closing. On PortAudio's thread that dropped some frames. On the event loop it would freeze the whole server. So sends queue, and one dedicated thread takes the risk. See `AgentHandle` in `session.py`.

**Barge-in clears two queues.** Telling the browser to flush while seconds of TTS still sit in the Python-side `Outbox` just means the pump refills it. `Outbox.drop_audio` walks the queue and removes the audio while leaving control frames alone, and it runs *before* the `clear` is queued. Both go through `call_soon_threadsafe`, which is FIFO, so that ordering holds. This is why `Outbox` is a `deque` and not an `asyncio.Queue` — you cannot selectively drop from a queue.

**The worklets do not assume a sample rate.** The page asks for an `AudioContext` at 24 kHz. Chrome and desktop Safari honour it; iOS Safari ignores it and can change rate mid-session when a Bluetooth headset connects. Both processors read the real rate back and resample when it differs, with an exact fast path for when it does not.

## Editing it

`uvx ruff check web` is part of `scripts/verify_steps.py`, and the repo enforces Google-style docstrings on every function. There is no build step, no bundler, and no npm: the static files are served as written, so a browser reload picks up a change to `app.js` immediately. Python changes need a restart.
