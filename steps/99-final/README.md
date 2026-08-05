# The finished agent

`main.py` in this folder is the completed workshop project — every step applied, nothing left as a TODO.

```bash
uv run steps/99-final/main.py
```

Use it as the reference implementation when a step of yours doesn't behave, or as the starting point for whatever you build next.

## What's in here

Roughly 350 lines, most of them comments, doing seven things:

| Concern | Where it lives |
|---|---|
| Audio format contract | `SAMPLE_RATE` / `CHANNELS` / `DTYPE` / `BLOCK_SIZE` |
| Turn detection | `EOT_THRESHOLD`, `EOT_TIMEOUT_MS`, wired into the listen provider |
| Agent definition | `SETTINGS` — listen, think, speak, greeting |
| Client-side functions | `FUNCTIONS`, `FUNCTION_HANDLERS`, `handle_function_call` |
| Inbound events | `on_message` |
| Barge-in | the `UserStartedSpeaking` branch |
| Outbound audio | `microphone_callback` |

The two threading rules the whole design rests on: `on_message` runs on the SDK's receive loop, and `microphone_callback` runs on PortAudio's realtime thread. Neither may block.

## Where to go from here

**Telephony.** Drop `SAMPLE_RATE` to 8000 and switch encoding to `mulaw` to match what phone networks carry. The rest of the file is unchanged — swapping the microphone and speaker for a Twilio media stream is the real work.

**Multilingual.** Change the listen model to `flux-general-multi` for automatic language detection, and pass `language_hints` when you know the likely languages. See [language prompting](https://developers.deepgram.com/docs/flux/language-prompting).

**Eager end-of-turn.** Add `eager_eot_threshold` (0.3–0.9, at or below `eot_threshold`) to start the LLM on a probable turn end and discard the work if the user keeps talking. Lower latency, more LLM calls.

**Keyterms.** Pass `keyterms` to the listen provider to bias recognition toward product names, SKUs, or jargon Flux would otherwise mishear. This is usually the highest-leverage accuracy fix for a domain-specific agent.

**Mid-conversation updates.** The socket accepts more than settings and media. `send_update_prompt` changes instructions without reconnecting, `send_inject_agent_message` makes the agent say something unprompted, and `send_inject_user_message` feeds it text as though the user spoke it — which also makes function calling testable without a microphone.

**Server-side functions.** Set `endpoint` on a `ThinkSettingsV1FunctionsItem` and Deepgram calls your HTTP API directly. No `FunctionCallRequest` reaches your client, which suits functions that don't need local state.

**Conversation context.** `AgentV1SettingsAgent` accepts a `context` with prior messages, so a returning caller can pick up where they left off.

## Reference

- [Voice Agent API](https://developers.deepgram.com/docs/voice-agent)
- [Flux](https://developers.deepgram.com/docs/flux) — the conversational speech-to-text model
- [TTS models](https://developers.deepgram.com/docs/tts-models) — the full voice list
- [API reference](https://developers.deepgram.com/reference/voice-agent-api/agent)

Questions land well in [Discord](https://discord.gg/xWRaCDBtW4) or [GitHub Discussions](https://github.com/orgs/deepgram/discussions).
