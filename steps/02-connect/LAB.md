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

You get `>> Connection opened`, five seconds of nothing, then `>> Connection closed`. A socket is open to Deepgram and neither side has said anything useful. Your job is to fix the second half of that.

Nothing from Step 1 carries forward — that was a diagnostic. The agent program starts here.

## The mental model

A traditional voice pipeline means three services and the glue between them: speech-to-text, an LLM, text-to-speech. You own the orchestration, the buffering, and every millisecond of latency between the hops.

The Voice Agent API collapses that into one WebSocket. You describe all three components in a single settings message, and Deepgram runs the pipeline server-side. Read `SETTINGS` in `main.py` top to bottom — it's the most important thing in the file:

- **`listen`** — Flux, Deepgram's conversational speech-to-text model. Turn detection lives *inside* the model, which is why you'll never write voice activity detection in this workshop.
- **`think`** — the LLM. `gpt-4o-mini` here, brokered by Deepgram, so your Deepgram key covers it.
- **`speak`** — Flux TTS. The `flux-` prefix routes to Deepgram's v2 Speak backend automatically.
- **`greeting`** — what the agent says first, added to the conversation history so the LLM knows it already said it.

Every later step in this workshop either adds to that object or reacts to what it produces.

> **Check yourself** — Which of the three models does `listen` configure, and where does the LLM get named?

## Do this

Work through the TODO blocks in `main.py` in order.

**TODO 2.1 — Handle inbound messages.** Create a `threading.Event` to signal the handshake, then write `on_message`. Two details in that handler matter more than they look:

The `isinstance(message, bytes)` check comes first because audio frames are not JSON events and have no `.type` attribute. Reach for one anyway and you get `"Unknown"` thousands of times a minute.

The final `else` prints instead of ignoring. Deepgram adds server events over time, and the fallthrough means new ones surface in your console rather than vanishing silently. You'll rely on that in Step 5.

**TODO 2.2 — Register the handler.** `agent.on(EventType.MESSAGE, on_message)`, and it has to land before `start_listening()` or the first events arrive with nobody listening.

**TODO 2.3 — Send the settings and wait.** Send `SETTINGS`, then block on the event until `SettingsApplied` comes back.

Do not skip the wait. The agent discards any media it receives before the handshake completes, so every later step opens the microphone *after* this line. Blocking here turns correct ordering into a guarantee instead of a race you win most of the time.

> **Check yourself** — Why must you wait for `SettingsApplied` before sending any audio?

## Verify

```
>> Connection opened
>> Welcome
Sending agent settings...
>> Settings applied

Agent is live. (Step 3 adds the speaker.)

[assistant] Hello! I'm a Deepgram voice agent. What would you like to talk about?
>> History
>> AgentAudioDone
>> Connection closed
```

The agent already spoke. That `[assistant]` line is `ConversationText`, and the audio for it streamed past your handler while you watched — you just have nowhere to play it yet.

Notice `>> Welcome` and `>> History` arriving through the fallthrough branch. Neither has an explicit `elif`, and both still showed up. That's the design working.

> **⏸ Pause — check in with the instructor**
> Everyone should see `>> Settings applied` and an `[assistant]` line before moving on. This is the first real milestone, and a failure here is almost always the API key.

## Stuck?

**`Timed out waiting for agent settings to apply`** — Either a rejected setting or a bad key. Check the console for an `Error` message just above the timeout.

**`CLIENT_MESSAGE_TIMEOUT` at the end** — Expected if you raised the sleep past about fifteen seconds. The agent expects a *continuous* media stream and hangs up when it receives none. Nothing sends audio until Step 4. Worth triggering once on purpose so you recognize it later.

**Nothing after `>> Connection opened`** — You registered the handler after `start_listening()`, or skipped `agent.send_settings(SETTINGS)`.

`steps/03-hear-the-agent/main.py` is this step, finished.

## Going further

Change `greeting` to something else and run again. Then delete it entirely — the agent connects and waits silently, which is what you want for an agent that answers rather than opens.

---

Your agent is live and already talking. Next you give it a speaker, and hear it.

**Next:** [Step 3 — Hear the agent](../03-hear-the-agent/LAB.md)
