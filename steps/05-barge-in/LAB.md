# Step 5 — Barge-in

**Goal:** Make the agent stop talking the moment you start.

**You'll learn**

- Why "the server stopped sending audio" and "the speaker stopped talking" are different events
- The difference between `abort()` and `stop()`, and why the polite-looking one is wrong
- What `UserStartedSpeaking` is actually telling you

## Start here — run it first

Before you write anything, run this file and **interrupt the agent mid-sentence**. Ask it something open-ended, wait for it to get going, then talk over it.

```bash
uv run steps/05-barge-in/main.py
```

It keeps going. Cheerfully, right across you, while the console prints `>> UserStartedSpeaking`. The server knew you'd started talking and told you immediately — your speaker just didn't care.

Sit with that for a second, because that gap is the entire step.

> **⏸ Pause — check in with the instructor**
> Do this part together. Everyone should hear the agent talk over them at least once before writing the fix — the bug is far more memorable than the patch.

## The mental model

By the time `UserStartedSpeaking` reaches your handler, a lot has already happened correctly. Flux detected start-of-turn inside the model. The agent stopped generating. The server stopped sending audio.

The problem is everything it *already* sent. Those frames are sitting in PortAudio's buffer, and they will play to completion — easily a second or two of the agent talking over you. Nothing upstream can help, because the audio has already left the building. Clearing that buffer is your job, and yours alone.

This is the client's one real obligation in a Flux voice agent. Everything else about turn-taking happens server-side.

## Do this

**TODO 5.1 — Add the `UserStartedSpeaking` branch.**

```python
speaker.abort()   # discard what is queued
speaker.start()   # reopen for the next reply
```

Use `abort()`, not `stop()`.

`stop()` **drains** the buffer — it plays everything already queued and *then* stops. That's precisely the behavior you're trying to eliminate. It's the single most common bug in a first voice agent, and it survives code review easily because `stop()` reads like the more polite call. `abort()` throws the queue away, which is exactly what an interrupted speaker should do.

> **Check yourself** — What does `stop()` do differently from `abort()`, and why is that wrong here?

Then `start()` again, because an aborted stream is closed and the next reply needs somewhere to land.

Wrap both in `try`/`except sd.PortAudioError` and print either way. A failed barge-in shouldn't end the conversation.

## Verify

Run it and talk over the agent again. It stops mid-word:

```
>> Agent started speaking
[assistant] The tallest mountain in the world is Mount Everest, which stands at approximately...
>> User started speaking (barge-in: playback cleared)
[user] What about the deepest ocean trench?
>> Agent thinking...
>> Agent started speaking
[assistant] The Mariana Trench, at about 36,000 feet.
```

The cut is immediate and a little abrupt — which is right. Human conversation works the same way.

**Use headphones for this.** Without them your speaker feeds your microphone, the agent interrupts itself, and you'll chase a bug that doesn't exist.

## Stuck?

**Still talks over you** — You used `stop()` instead of `abort()`. Read them side by side; the names are nearly interchangeable and the behaviors are opposites.

**First interruption works, then silence forever** — You called `abort()` without `start()`. The stream is closed and every later write goes nowhere.

**The agent interrupts itself constantly** — Speaker bleeding into microphone. Headphones. If you're stuck on laptop speakers, turn the volume down and expect some of this.

**`barge-in failed: ...`** — Your `except` branch caught a `PortAudioError`. The conversation survives, which is the point, but check whether your device is being shared with another application.

**It cuts you off too eagerly, mid-thought** — That's turn detection, not barge-in, and it's exactly what Step 6 tunes.

`steps/06-tune-turns/main.py` is this step, finished.

## Going further

Swap `abort()` for `stop()` deliberately and interrupt the agent a few times. Time how long it keeps talking. That interval is what every voice agent that feels "laggy" or "rude" is actually suffering from, and you can now recognize it by ear in someone else's product.

---

Your agent listens, thinks, speaks, and yields the floor. What's left is making the turn-taking feel natural.

**Next:** [Step 6 — Tune turn detection](../06-tune-turns/LAB.md)
