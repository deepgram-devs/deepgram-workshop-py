# Step 4 — Talk to the agent

**Goal:** Stream microphone audio to the agent and hold an actual conversation.

**You'll learn**

- How Flux decides where your turns begin and end without any client-side help
- Why 80 ms is the chunk size, and what moving it costs in both directions
- Why a send that blocks is a bigger problem than it looks

## Start here

```bash
uv run steps/04-talk-to-the-agent/main.py
```

Press **Connect**. The greeting plays, the level meter moves when you talk — the microphone really is open — and then, about fifteen seconds later, the agent hangs up. It is waiting to hear from you and nothing is sending it anything.

This is the step where it becomes a voice agent.

## The mental model

The microphone lives in the browser and has been open since you pressed Connect. What is missing is the instruction to do anything with what it captures.

That instruction is `on_media`, and it is one line:

```python
def on_media(agent, audio):
    agent.send_media(audio)
```

The shortness is the lesson. Here is the part that surprises people coming from traditional speech pipelines: there is no voice activity detection anywhere in this file. No silence trimming, no energy threshold, no "has the user stopped talking" logic. Flux performs turn detection **inside the model**, server-side. Your entire job on the outbound side is keeping the pipe full and letting Flux decide the rest.

Two things happen before the audio reaches you, both in `CaptureProcessor` in [`web/static/worklets.js`](../../web/static/worklets.js), and both are work you would otherwise be doing yourself:

**Chunking.** Audio hardware delivers 128 frames at a time — about 5 ms. Flux wants 80 ms, which is 1920 frames at 24 kHz, exactly fifteen of those blocks. The worklet accumulates and ships a chunk when it is full.

**Resampling.** Most microphones run at 48 kHz. `SETTINGS` asked for 24 kHz. The page creates its `AudioContext` at 24 kHz so the browser's own resampler handles it — and carries a fallback for the browsers that ignore the request, which is why `CaptureProcessor` has a `ratio` at all.

> **Check yourself** — Traditional voice pipelines need voice activity detection in the client. Why doesn't this one?

## Do this

**TODO 4.1 — Write `on_media`.** One call: `agent.send_media(audio)`.

Note that it does not block. `agent` here is not the SDK's socket — it is an `AgentHandle` ([`web/session.py`](../../web/session.py)) that hands the chunk to a dedicated sender thread and returns.

That indirection exists for a specific reason worth knowing. The underlying `websockets` library joins its receive thread when a connection starts closing, with a ten-second default timeout. So the moment Deepgram hangs up, the *next* send blocks its caller for up to ten seconds. On a realtime audio thread that means dropped frames. On the web server's event loop it would freeze everything — the playback pump, the page, the lot. One thread takes that risk so nothing else has to.

**TODO 4.2 — Pass it to the bridge.** Add `on_media=on_media` to the `bridge.run(...)` call.

Passing it is what tells the page to start capturing, and *when* it starts matters: only after `SettingsApplied` arrives. The agent discards media received before the handshake completes, so starting any earlier throws away your first words. The bridge enforces that — it is why the page waits for a `ready` message instead of sending audio as soon as the socket opens.

## Verify

Run it and talk. You should hear the greeting, ask a question, and get a spoken answer:

```
>> Settings applied

[assistant] Hello! I'm a Deepgram voice agent. What would you like to talk about?
>> Agent finished speaking
>> UserStartedSpeaking
[user] What's the tallest mountain in the world?
>> Agent thinking...
>> Agent started speaking
[assistant] Mount Everest, at about 29,032 feet.
>> Agent finished speaking
```

The transcript builds up on the page too. Ctrl+C in the terminal exits cleanly.

Two things to notice. First, `>> UserStartedSpeaking` appears with no branch handling it — that's the Step 2 fallthrough earning its place, and it becomes the whole point of Step 5. Second, the `CLIENT_MESSAGE_TIMEOUT` from earlier steps is gone. Once you're streaming audio continuously, the agent has no reason to hang up.

> **⏸ Pause — check in with the instructor**
> Everyone should have held a real conversation. This is the high point of the workshop — take a minute, let people ask it something silly, and make sure nobody is left behind before Step 5.

## Stuck?

**The agent never responds to you** — Does the level meter move when you talk? If it does not, the microphone is muted or the browser picked the wrong input. If it does, check that you passed `on_media=on_media` and not just defined the function.

**"connected, not sending audio" stays on the page** — TODO 4.2 is not done. That message is the bridge telling you `on_media` was never passed.

**The agent hears itself and answers its own questions** — Your speaker is feeding your microphone. The browser's echo cancellation handles most of this, but not all of it on every browser. Use headphones. This gets much more noticeable in Step 5.

**Long pause before the agent replies** — Normal at this stage. Step 6 shows you how to measure it and what moves it.

`steps/05-barge-in/main.py` is this step, finished.

## Going further

In `CaptureProcessor`, change `chunkFrames` to a quarter of what the bridge sends it — around 20 ms — and hold a conversation. Then try five times it, half a second. The short chunks pay WebSocket overhead for no benefit; the long ones make turn detection visibly sluggish, because Flux cannot score an end-of-turn until the chunk containing it arrives. 80 ms sits where it does for a reason.

---

You have a working two-way conversation. Now try interrupting it, and find out what's still missing.

**Next:** [Step 5 — Barge-in](../05-barge-in/LAB.md)
