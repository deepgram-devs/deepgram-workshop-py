# Step 3 — Hear the agent

**Goal:** Route the agent's Flux TTS audio to your speaker and hear the greeting out loud.

**You'll learn**

- Why a "raw" PortAudio stream is the natural fit for socket audio
- What happens when your audio format and the agent's disagree
- Why an exception in a message handler ends the entire call

## Start here

```bash
uv run steps/03-hear-the-agent/main.py
```

Everything from Step 2 works. The agent connects, applies settings, and announces itself in the console. Audio for that greeting is arriving on the socket right now, and the `isinstance(message, bytes)` branch is throwing every frame away.

This step gives it somewhere to go.

## The mental model

Deepgram sends TTS audio as raw PCM frames matching the `output` format you declared in `SETTINGS`: 24 kHz, mono, signed 16-bit. No container, no header, no decoding — the bytes off the socket are already playable samples.

That maps directly onto `sd.RawOutputStream`. The "raw" variant accepts `bytes` rather than NumPy arrays, so audio goes from socket to speaker with nothing in between. Hand it a chunk, PortAudio queues it, your speaker plays it.

The three constants at the top of the file (`SAMPLE_RATE`, `CHANNELS`, `DTYPE`) have to match the `output` settings exactly. When they disagree you don't get an error — you get audio at the wrong speed and pitch, which is a memorable way to learn this lesson and an annoying way to spend ten minutes.

> **Check yourself** — Why do you open the speaker stream *before* sending settings rather than after?

## Do this

**TODO 3.1 — Import `sounddevice`.** It goes with the other third-party imports, alphabetized. `sounddevice` ships PortAudio binaries inside its wheels for Linux, macOS, and Windows, which is the entire reason this workshop uses it — there's nothing to install at the system level.

**TODO 3.2 — Open the speaker.** Create the stream and start it *before* the handlers below it. With a greeting configured, the first audio frame lands within milliseconds of `SettingsApplied`, so the stream needs to already exist.

**TODO 3.3 — Play the audio.** Write the frames to the speaker inside a `try`/`except sd.PortAudioError`.

Catch that exception rather than letting it fly. Your handler runs inside the SDK's receive loop, and that loop wraps everything in a single `try`/`except` — so any exception escaping your handler gets reported as `EventType.ERROR` and closes the connection. Dropping one 80 ms chunk beats ending the call.

**TODO 3.4 — Narrate the turn.** Give `AgentThinking`, `AgentStartedSpeaking`, and `AgentAudioDone` their own branches so the console reads like a transcript of what the agent is doing.

`LatencyReport` gets an explicit `pass`. It fires once per turn, and left to the fallthrough it clutters the transcript. Step 6 turns it into something you'll actually want.

**TODO 3.5 — Release the device.** Add `finally: speaker.stop()` so the stream closes even after Ctrl+C. Leaving PortAudio streams open is how you end up restarting your terminal to get audio back.

## Verify

You hear the greeting spoken aloud, and the console shows:

```
>> Settings applied

Listening to the greeting... (Step 4 opens the microphone)

[assistant] Hello! I'm a Deepgram voice agent. What would you like to talk about?
>> Agent finished speaking
>> Connection closed
```

`>> AgentAudioDone` now reads `>> Agent finished speaking`, and the timing lines up with the audio ending.

> **⏸ Pause — check in with the instructor**
> Everyone should hear the greeting out loud. Silent machines need fixing now — Step 4 is much harder to debug when you cannot hear anything.

## Stuck?

**Silence, but no errors** — Check your output device with `uv run steps/01-setup/main.py`. Then confirm `speaker.start()` is actually being called; creating the stream isn't enough.

**Audio plays too fast, too slow, or chipmunk-pitched** — Your stream's `samplerate` doesn't match the `output` sample rate in `SETTINGS`. Both are 24000.

**Stuttering or crackling** — Another process is competing for the audio device, or you added something slow inside the bytes branch. That branch runs on the SDK's receive loop; keep it to the write.

**`>> Dropped audio chunk`** — Your error handling is working. An occasional one is fine; a flood means the device is struggling.

`steps/04-talk-to-the-agent/main.py` is this step, finished.

## Going further

Comment out `speaker.start()` and run it. The stream exists, the writes go somewhere, and nothing plays — a good reminder that PortAudio streams are inert until started.

---

You can hear the agent. Now close the loop and let it hear you.

**Next:** [Step 4 — Talk to the agent](../04-talk-to-the-agent/LAB.md)
