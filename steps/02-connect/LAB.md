# Step 2 — Connect

**Goal:** Open a WebSocket to the Voice Agent API, describe the agent you want, and confirm the server accepted it.

**You'll learn**

- How one `AgentV1Settings` object configures listening, thinking, and speaking
- Why the settings handshake has to complete before you send a single byte of audio
- How to write a message handler that survives events Deepgram hasn't shipped yet

## Start here

This folder runs as-is:

```bash
uv run steps/02-connect/main.py
```

A page opens with a **Connect** button. Press it and you get `>> Connection opened` in the terminal, a handshake, and then nothing useful — the settings go out and every reply is thrown away. Your job is to fix the second half of that.

Nothing from Step 1 carries forward — that was a diagnostic. The agent program starts here.

## The mental model

A traditional voice pipeline means three services and the glue between them: speech-to-text, an LLM, text-to-speech. You own the orchestration, the buffering, and every millisecond of latency between the hops.

The Voice Agent API collapses that into one WebSocket. You describe all three components in a single settings message, and Deepgram runs the pipeline server-side. Read `SETTINGS` in `main.py` top to bottom — it's the most important thing in the file:

- **`listen`** — Flux, Deepgram's conversational speech-to-text model. Turn detection lives *inside* the model, which is why you'll never write voice activity detection in this workshop.
- **`think`** — the LLM. `gpt-4o-mini` here, brokered by Deepgram, so your Deepgram key covers it.
- **`speak`** — Flux TTS. The `flux-` prefix routes to Deepgram's v2 Speak backend automatically.
- **`greeting`** — what the agent says first, added to the conversation history so the LLM knows it already said it.

Every later step in this workshop either adds to that object or reacts to what it produces.

### Where the browser fits

Your `main.py` never touches a microphone, a speaker, or a socket. It hands two things to `bridge.run()` — the agent you want, and a function to call when the agent says something — and the shared code in [`web/`](../../web/) does the rest.

That is not a shortcut around the interesting part; it is a boundary worth knowing the shape of. Open [`web/session.py`](../../web/session.py) and find `_run()`. Every line of connection ordering the rest of this workshop depends on is in that one function:

```
open the socket
  → register handlers        (before listening, or the first events go nowhere)
  → start the listener       (the receive loop blocks, so it gets a thread)
  → send SETTINGS
  → wait for SettingsApplied (up to ten seconds)
  → only now: tell the browser it may capture
```

You will write that sequence yourself the first time you build one of these without a bridge. Read it now while it is small.

> **Check yourself** — Which of the three models does `listen` configure, and where does the LLM get named?

## Do this

Work through the TODO blocks in `main.py` in order.

**TODO 2.1 — Handle inbound messages.** Write `on_message`. Three details in that handler matter more than they look:

The `isinstance(message, bytes)` check comes first because audio frames are not JSON events and have no `.type` attribute. Reach for one anyway and you get `"Unknown"` thousands of times a minute.

The final `else` prints instead of ignoring. Deepgram adds server events over time, and the fallthrough means new ones surface in your console rather than vanishing silently. You'll rely on that in Step 5.

The signature takes three arguments — `agent`, `player`, `message` — whether you use them or not. `player` starts earning its place in Step 3, `agent` in Step 8.

**TODO 2.2 — Hand your agent to the bridge.** `bridge.run(settings=SETTINGS, on_message=on_message)`.

Note what you are *not* passing: `on_media`. Without it the bridge never opens the microphone at all, which is why this step sends no audio — and why the agent hangs up on you.

> **Check yourself** — The bridge waits for `SettingsApplied` before it lets the browser send audio. Why does that ordering matter?

## Verify

```
>> Connection opened
>> Welcome
Sending agent settings...
>> Settings applied
[assistant] Hello! I'm a Deepgram voice agent. What would you like to talk about?
>> History
>> AgentAudioDone
>> Agent error: CLIENT_MESSAGE_TIMEOUT - ...
>> Connection closed
```

The agent already spoke. That `[assistant]` line is `ConversationText`, and the audio for it streamed past your handler while you watched — you just have nowhere to play it yet. It also appears in the transcript on the page, which is the bridge mirroring events for you, not your code.

Notice `>> Welcome` and `>> History` arriving through the fallthrough branch. Neither has an explicit `elif`, and both still showed up. That's the design working.

The `CLIENT_MESSAGE_TIMEOUT` at the end is expected. The agent wants a *continuous* media stream and hangs up after about fifteen seconds of receiving none. Nothing sends audio until Step 4. Worth seeing now so you recognise it later.

> **⏸ Pause — check in with the instructor**
> Everyone should see `>> Settings applied` and an `[assistant]` line before moving on. This is the first real milestone, and a failure here is almost always the API key.

## Stuck?

**The page says the server timed out applying settings** — Either a rejected setting or a bad key. Check the terminal for an `Error` message just above it.

**Nothing after `>> Connection opened`** — You defined `on_message` but did not pass it to `bridge.run`.

**The Connect button is disabled** — Read the red box on the page. Almost always a page opened on a LAN address rather than `127.0.0.1`.

**`Address already in use`** — An earlier step is still running in another terminal. Stop it, or pass `--port 8001`.

`steps/03-hear-the-agent/main.py` is this step, finished.

## Going further

Change `greeting` to something else and run again. Then delete it entirely — the agent connects and waits silently, which is what you want for an agent that answers rather than opens.

---

Your agent is live and already talking. Next you give the audio somewhere to go, and hear it.

**Next:** [Step 3 — Hear the agent](../03-hear-the-agent/LAB.md)
