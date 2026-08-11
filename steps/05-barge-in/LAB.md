# Step 5: Barge-in

**Goal:** Make the agent stop talking the moment you start.

**You'll learn**

- Why "the server stopped sending audio" and "the speaker stopped talking" are different events
- That more than one queue sits between the agent and your ears, and why clearing one is not enough
- What `UserStartedSpeaking` is actually telling you

## Start here

Before you write anything, run this file and **interrupt the agent mid-sentence**. Ask it something open-ended, wait for it to get going, then talk over it.

```bash
uv run steps/05-barge-in/main.py
```

It keeps going. Cheerfully, right across you, while the console prints `>> UserStartedSpeaking`. The server knew you'd started talking and told you immediately. Your speaker just didn't care.

Sit with that for a second, because that gap is the entire step.

> **⏸ Pause: check in with the instructor**
> Do this part together. Everyone should hear the agent talk over them at least once before writing the fix, because the bug is far more memorable than the patch.

## The mental model

`UserStartedSpeaking` arrives only after the server has already done its part. Flux detected start-of-turn inside the model. The agent stopped generating. The server stopped sending audio.

The problem is everything it *already* sent. The agent produced every byte of that before you opened your mouth, and all of it is still on its way to your ears, easily a second or two of the agent talking over you. Nothing upstream can help, because that audio has already left the building. Throwing it away is your job, and yours alone.

This is the client's one real obligation in a Flux voice agent. Everything else about turn-taking happens server-side.

Here is the part that catches people: **two queues sit between the agent and your ears**, and clearing only one leaves the bug in place.

```mermaid
flowchart LR
    DG([Deepgram]) --> PY[["queue in Python<br/>Outbox in web/audio.py"]]
    PY --> WS([WebSocket])
    WS --> BR[["queue in the browser<br/>PlaybackProcessor in worklets.js"]]
    BR --> SPK([speaker])

    classDef queue stroke-width:3px
    class PY,BR queue
```

Tell the browser to flush while seconds of TTS still sit in the Python queue and the pump simply refills it. The agent talks over you a moment later instead of immediately, which is worse, because now it looks like it *nearly* works.

`player.clear()` does both, in the order that matters: drop the Python side **first**, then send the browser its instruction. Read `BrowserPlayer.clear` and `Outbox.drop_audio` in [`web/audio.py`](../../web/audio.py). Note that `drop_audio` removes only the audio frames and leaves control messages alone, and note the comment explaining why the ordering holds across threads.

## Do this

**TODO 5.1: Add the `UserStartedSpeaking` branch.**

```python
elif message_type == "UserStartedSpeaking":
    player.clear()
    print(">> User started speaking (barge-in: playback cleared)")
```

> **Check yourself:** Why does `clear()` drop the Python-side queue before telling the browser, rather than after?

**The trap, if you ever write this yourself.** On the `--local` path the same call has to reach for PortAudio, and there the choice is `abort()` versus `stop()`. `stop()` **drains** the buffer. It plays everything already queued and *then* stops, which is precisely the behavior you are trying to eliminate. It is the single most common bug in a first voice agent, and it survives code review easily because `stop()` reads like the more polite call. See `LocalPlayer.clear` in [`web/audio.py`](../../web/audio.py).

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

The cut is immediate and a little abrupt, which is right. Human conversation works the same way.

Your browser cancels most of the echo from your speakers, which is why this step no longer requires headphones. It is not perfect on every browser, though, and this is the step where the difference shows. If the agent starts interrupting itself, that is echo rather than a bug in your code. Headphones eliminate this echo.

## Stuck?

**Still talks over you, but only briefly.** You cleared one queue and not the other. If you wrote your own clear, this is the Python-side `Outbox` you forgot.

**Nothing changes at all.** Check that the branch actually runs. `>> User started speaking` should print; if you only see the bare `>> UserStartedSpeaking` fallthrough, the branch is in the wrong place or misspelled.

**The agent interrupts itself constantly.** Speaker bleeding into microphone, past the echo canceller. Use headphones. If you're stuck on laptop speakers, turn the volume down and expect some of this.

**It cuts you off too eagerly, mid-thought.** That's turn detection rather than barge-in, and it's exactly what Step 8 tunes.

`steps/06-make-it-yours/main.py` is this step, finished.

## Going further

Comment out the `this.queue.length = 0` line in `PlaybackProcessor`'s `clear` handler, leaving the Python-side drop in place. Interrupt the agent. You have just built the half-fixed version, the one that clears the queue you can see and forgets the one you cannot. Time how long it keeps talking. That interval is what every voice agent that feels "laggy" or "rude" is actually suffering from, and you can now recognize it by ear in someone else's product.

---

Your agent listens, thinks, speaks, and yields the floor. What it doesn't have is a personality. Right now it's a stock assistant with a stock voice.

**Next:** [Step 6: Make it yours](../06-make-it-yours/LAB.md)
