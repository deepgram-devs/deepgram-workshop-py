# Step 3 — Hear the agent

**Goal:** Route the agent's Flux TTS audio to your speaker and hear the greeting out loud.

**You'll learn**

- Why streaming audio always needs a queue, and who owns it
- The difference between "the agent stopped sending" and "you stopped hearing"
- Why an exception in a message handler ends the entire call

## Start here

```bash
uv run steps/03-hear-the-agent/main.py
```

Press **Connect**. Everything from Step 2 works: the agent connects, applies settings, and announces itself in the console. Audio for that greeting is arriving on the socket right now, and the `isinstance(message, bytes)` branch is throwing every frame away.

This step gives it somewhere to go.

## The mental model

Deepgram sends TTS audio as raw PCM frames matching the `output` format you declared in `SETTINGS`: 24 kHz, mono, signed 16-bit. No container, no header, no decoding — the bytes off the socket are already playable samples.

Your handler's second argument, `player`, is where they go. One call:

```python
player.send(message)
```

What makes that one line rather than fifty is a queue, and it is worth knowing where it is, because you will write one yourself the next time you build a voice agent without a bridge like this.

Audio arrives from the network in **bursts** — several hundred milliseconds at a time, whenever Flux finishes synthesising a chunk. It is consumed at a **constant** rate: your sound hardware asks for exactly 128 samples every 5.3 ms and will not wait. Something has to absorb that difference, and if it ever runs dry you hear a click.

Open [`web/static/worklets.js`](../../web/static/worklets.js) and read `PlaybackProcessor`. It is about forty lines and it is the whole story:

- `this.queue` — an array of chunks waiting to be heard.
- `process()` — hands the hardware exactly as many samples as it asked for, then fills any shortfall with **silence** rather than stale audio.
- `return true` at the end, unconditionally. Return `false` and the browser garbage-collects the node after one idle quantum, and the next reply has nowhere to go.

That queue is why `AgentAudioDone` does not mean "the agent stopped talking." It means the agent stopped *sending*. There may still be a second of speech queued ahead of you. Step 5 is entirely about that gap.

> **Check yourself** — The bridge waits for the browser's speaker to exist before it opens the Deepgram socket. What would go wrong if it connected first?

## Do this

**TODO 3.1 — Play the audio.** Replace the discarded branch with `player.send(message)`.

Notice what you are *not* writing: no error handling, no buffering, no device setup. A chunk that cannot be played is the bridge's problem. Look at `LocalPlayer.send` in [`web/audio.py`](../../web/audio.py) to see the version that does have to care — it catches `PortAudioError` and drops the chunk rather than letting it fly, because that handler runs inside the SDK's receive loop, and that loop wraps everything in a single `try`/`except`. Any exception escaping it gets reported as `EventType.ERROR` and closes the connection. Dropping one 80 ms chunk beats ending the call.

**TODO 3.2 — Narrate the turn.** Give `AgentThinking`, `AgentStartedSpeaking`, and `AgentAudioDone` their own branches so the console reads like a transcript of what the agent is doing.

`LatencyReport` gets an explicit `pass`. It fires once per turn, and left to the fallthrough it clutters the transcript. Step 6 turns it into something you'll actually want.

## Verify

You hear the greeting spoken aloud, the transcript appears on the page, and the console shows:

```
>> Settings applied

[assistant] Hello! I'm a Deepgram voice agent. What would you like to talk about?
>> Agent started speaking
>> Agent finished speaking
>> Agent error: CLIENT_MESSAGE_TIMEOUT - ...
>> Connection closed
```

`>> AgentAudioDone` now reads `>> Agent finished speaking`. Watch when it prints: **before** the audio finishes playing. That is the queue.

The `CLIENT_MESSAGE_TIMEOUT` at the end is expected and is the last time you will see it. The agent wants a continuous media stream and this step sends none, so it hangs up after about fifteen seconds. Step 4 fixes that by giving it something to listen to.

> **⏸ Pause — check in with the instructor**
> Everyone should hear the greeting out loud. Silent machines need fixing now — Step 4 is much harder to debug when you cannot hear anything.

## Stuck?

**Silence, but no errors** — Check the browser console (F12). Then re-run `uv run steps/01-setup/main.py` and press "Run the audio checks"; the tone test tells you whether the problem is this step or your output device.

**Nothing happens when you press Connect** — Look for a red box on the page. The most common cause is opening the page on a LAN address rather than `127.0.0.1`; browsers only grant microphone and AudioWorklet access on a secure context.

**Audio plays too fast, too slow, or chipmunk-pitched** — The page and `SETTINGS` disagree about the sample rate. Both read it from `SAMPLE_RATE`, so this should be impossible; if you see it, check the browser console for a warning about the rate the browser actually gave you.

**Stuttering or crackling** — You added something slow inside the bytes branch. It runs on the SDK's receive loop; keep it to the one call.

`steps/04-talk-to-the-agent/main.py` is this step, finished.

## Going further

In `PlaybackProcessor.process`, change the underrun fill from `0` to something audible — repeat the last sample instead of writing silence. Run it and listen to a reply. That buzz is what a naive playback queue sounds like when it runs dry, and it is why the real one writes silence.

---

You can hear the agent. Now close the loop and let it hear you.

**Next:** [Step 4 — Talk to the agent](../04-talk-to-the-agent/LAB.md)
