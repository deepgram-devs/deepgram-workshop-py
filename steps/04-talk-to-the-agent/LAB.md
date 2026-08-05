# Step 4 — Talk to the agent

**Goal:** Stream microphone audio to the agent and hold an actual conversation.

**You'll learn**

- Why a PortAudio callback must never block, and what happens when it does
- Why `bytes(indata)` copies, and the bug you get when it doesn't
- How Flux decides where your turns begin and end without any client-side help

## Start here

```bash
uv run steps/04-talk-to-the-agent/main.py
```

The greeting plays, then the program sits quiet for ten seconds and exits. The agent is waiting to hear from you and nothing is sending it anything.

This is the step where it becomes a voice agent.

## The mental model

`sounddevice` hands you captured audio through a callback that PortAudio invokes on its own high-priority realtime thread, on a strict schedule. Every 80 ms it calls your function with a fresh block and expects you back promptly. Miss that deadline and you get dropouts and glitches — audible ones.

That constraint shapes the whole design. The callback body is one non-blocking send and nothing else. No processing, no buffering, no inspection of the audio.

Here's the part that surprises people coming from traditional speech pipelines: there's no voice activity detection anywhere in this file. No silence trimming, no energy threshold, no "has the user stopped talking" logic. Flux performs turn detection inside the model, server-side. Your entire job on the outbound side is keeping the pipe full and letting Flux decide the rest.

## Do this

Everything in this step goes *below* the settings handshake. That placement matters: the agent discards media until `SettingsApplied` arrives, so opening the microphone any earlier throws away your first words. The `settings_applied.wait(10)` you wrote in Step 2 is what makes that ordering reliable.

**TODO 4.1 — Write the callback.** Three things in that tiny body carry weight:

`bytes(indata)` **copies**. PortAudio reuses the underlying memory as soon as your callback returns, so passing the buffer along unmodified hands the socket a view of audio that's about to be overwritten. You'd hear the symptom as garbled or repeated audio and spend a long time blaming the network.

**The body stays minimal.** One send. See the realtime-thread constraint above.

**`sd.CallbackAbort` on failure.** A stray exception kills the stream and then resurfaces out of `microphone.stop()` during shutdown, burying the real cause under an unrelated traceback. A dead socket has nowhere left to send audio, so stop capturing deliberately.

**TODO 4.2 — Open the input stream.** It mirrors the speaker, plus `blocksize=BLOCK_SIZE` and your callback.

`BLOCK_SIZE` is 80 ms of audio, the chunk size Flux is tuned for. Smaller blocks pay WebSocket overhead on every chunk. Larger blocks delay turn detection, because Flux can't score an end-of-turn until the block containing it arrives.

**TODO 4.3 — Run until interrupted.** Replace the fixed sleep with a loop, and add `microphone.stop()` to the `finally`.

The main thread now does nothing but idle. Every interesting thing happens on the listener thread (inbound) and PortAudio's threads (outbound).

## Verify

Run it and talk. You should hear the greeting, ask a question, and get a spoken answer:

```
>> Settings applied

Listening... press Ctrl+C to exit.

[assistant] Hello! I'm a Deepgram voice agent. What would you like to talk about?
>> Agent finished speaking
>> UserStartedSpeaking
[user] What's the tallest mountain in the world?
>> Agent thinking...
>> Agent started speaking
[assistant] Mount Everest, at about 29,032 feet.
>> Agent finished speaking
```

Ctrl+C exits cleanly.

Two things to notice. First, `>> UserStartedSpeaking` appears with no branch handling it — that's the Step 2 fallthrough earning its place, and it becomes the whole point of Step 5. Second, the `CLIENT_MESSAGE_TIMEOUT` from earlier steps is gone. Once you're streaming audio continuously, the agent has no reason to hang up.

## Stuck?

**The agent never responds to you** — The microphone opened but isn't reaching the socket. Check that `agent.send_media(bytes(indata))` is actually in the callback, and that the stream was `.start()`ed.

**Garbled or repeated audio reaching the agent** — You passed `indata` without wrapping it in `bytes()`.

**Dropouts, glitches, or `input overflow`** — Something slow crept into the callback. Move it out.

**The agent hears itself and answers its own questions** — Your speaker is feeding your microphone. Use headphones. This gets much more noticeable in Step 5.

**Long pause before the agent replies** — Normal at this stage. Step 6 shows you how to measure it and what moves it.

`steps/05-barge-in/main.py` is this step, finished.

## Going further

Set `BLOCK_SIZE` to `SAMPLE_RATE * 500 // 1000` — half-second blocks — and hold a conversation. Turn detection gets noticeably sluggish, because Flux is waiting on your chunks. Then try 10 ms blocks and watch the WebSocket traffic climb for no benefit. 80 ms sits where it does for a reason.

---

You have a working two-way conversation. Now try interrupting it, and find out what's still missing.

**Next:** [Step 5 — Barge-in](../05-barge-in/LAB.md)
