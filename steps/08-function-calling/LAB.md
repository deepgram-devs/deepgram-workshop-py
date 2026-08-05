# Step 8 — Function calling

**Goal:** Let the agent run your Python and speak the result.

**You'll learn**

- What makes a function client-side, and why that's a single omitted field
- Why the function description *is* a prompt
- The threading trap that turns a slow function into stuttering audio

## Start here

```bash
uv run steps/08-function-calling/main.py
```

You have a complete voice agent. Ask it what time it is and it will confidently make something up, because an LLM has no clock. This step closes that gap and every gap like it.

## The mental model

Function calling connects the agent to things the model can't know: your database, your API, the current time, the user's order history. The flow has four hops.

1. You advertise a function in `SETTINGS` — name, description, and a JSON Schema for its parameters.
2. The LLM decides a user turn warrants calling it, and Deepgram sends you a `FunctionCallRequest`.
3. Your code runs the function and sends back a `FunctionCallResponse`.
4. The LLM works your result into its reply, and the agent speaks it.

The single most important detail: **leaving `endpoint` unset marks a function client-side.** That one omission is what makes Deepgram send the call down the socket to you, instead of calling an HTTP endpoint itself. Set `endpoint` and Deepgram handles the call server-side and you never see it. Both are valid; client-side is what you want when the function touches local state, local credentials, or anything you'd rather not expose over HTTP.

The second most important detail: **the description is a prompt.** It's the only thing the LLM reads when deciding whether to call your function. Write it to say *when* to use the function, not just what it does. "Get the current time" is worse than "Get the current date and time in a given IANA timezone. Use this whenever the user asks what time it is or what today's date is."

## Do this

**TODO 8.1 — Add the imports.** Four of them, listed in the file.

**TODO 8.2 — Write the function.** `get_current_time(timezone)`, building a `ZoneInfo` with a UTC fallback in a `try`/`except`.

That fallback isn't defensive padding. The LLM invents plausible-but-wrong timezone strings often enough — `"EST"`, `"Pacific"`, `"Tokyo"` — that raising here would end otherwise fine conversations.

Return a **sentence**, not a data structure. Whatever you return goes back to the LLM and gets read aloud, so `"It is 2:15 PM on Tuesday, August 05 in America/New_York."` works far better than `{"hour": 14, "minute": 15}`.

One portability note: `strftime`'s `%-I` (hour without a leading zero) is a glibc/BSD extension that fails on Windows. Use `"%I:%M %p"` and `.lstrip("0")`.

**TODO 8.3 — Advertise it.** Build the `FUNCTIONS` list. The `parameters` field is plain JSON Schema, exactly as the LLM's tool-calling API expects.

**TODO 8.4 — Attach it.** `functions=FUNCTIONS` on `ThinkSettingsV1`.

**TODO 8.5 — Handle the call.** Write `handle_function_call`. Two things will bite you here:

**Catch exceptions and return the error text as `content`.** The agent is mid-turn and blocked waiting on your response. A raised exception escapes into the SDK's receive loop, surfaces as `EventType.ERROR`, and drops the call. Returning `"get_current_time failed: ..."` lets the LLM apologize gracefully and move on.

**This runs on the SDK's receive loop — the same thread delivering audio.** A slow function stalls playback for the whole conversation. Keep handlers fast, or hand the work to a thread and reply when it finishes. This is a real production failure mode, not a workshop artifact.

Print both the call and the result. You want to see what the LLM actually passed you.

**TODO 8.6 — Dispatch it.** Add the `FunctionCallRequest` branch.

Run it *before* you add this branch, once. You'll see `>> FunctionCallRequest` from the fallthrough and then nothing — the agent waits forever for a reply that never comes. Worth seeing on purpose, because it's what a broken handler looks like from the outside.

## Verify

Ask it what time it is in Tokyo:

```
[user] What time is it in Tokyo right now?
>> Function call: get_current_time({"timezone":"Asia/Tokyo"})
>> Function result: It is 2:26 AM on Thursday, August 06 in Asia/Tokyo.
>> Agent thinking...
[assistant] It is 2:26 AM on Thursday, August 6 in Tokyo.
```

Notice the LLM translated "Tokyo" into the IANA identifier `Asia/Tokyo` on its own. That's the schema description doing its job.

Then ask it something that shouldn't trigger a call — "what's the capital of France?" — and confirm no function fires. An agent that calls functions it doesn't need is as broken as one that never calls them.

## Stuck?

**The function never gets called** — Nine times out of ten it's the description. Make it explicit about *when* to use the function. Confirm `functions=FUNCTIONS` actually reached `ThinkSettingsV1`.

**`>> FunctionCallRequest` prints and the agent goes silent** — TODO 8.6 isn't done, or your handler raised before sending a response. The agent is still waiting.

**`TypeError: got an unexpected keyword argument`** — The LLM passed a parameter your Python doesn't accept. Your schema and your signature have drifted apart.

**Audio stutters when a function runs** — The threading trap. Your handler is too slow for the receive loop.

**Agent gets the answer but says something different** — The LLM paraphrases your result. Return a clear, complete sentence and it stays close to it.

`steps/99-final/main.py` is this step, finished.

## Going further

Add a second function and watch the LLM choose between them. Good candidates: a fake order lookup keyed by a number the user reads aloud, a unit converter, a `roll_dice(sides, count)` for the dungeon-master persona from Step 7.

Then break one on purpose — raise an exception inside it — and listen to how the agent handles the failure. Graceful degradation is most of what separates a demo from something you'd ship.

---

You've built a complete voice agent: it listens on Flux, thinks with an LLM, speaks with Flux TTS, yields the floor when interrupted, and calls your code when it needs something it can't know.

**Next:** [Where to go from here](../99-final/README.md)
