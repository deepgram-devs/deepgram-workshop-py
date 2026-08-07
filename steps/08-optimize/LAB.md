# Step 8 — Optimization

**Goal:** Make the agent you just built feel fast, and know what it cost you.

**You'll learn**

- How to read `LatencyReport` and which number actually matters
- What `eot_threshold` and `eot_timeout_ms` trade against each other
- Why `eager_eot_threshold` buys latency with LLM calls

## Start here

```bash
uv run steps/08-optimize/main.py
```

Your agent is finished. It listens, thinks, speaks, yields the floor when you interrupt, and calls your Python when it needs something it can't know. Everything from here is how it *feels*.

This step is dials rather than code — and it's the step that decides whether people enjoy talking to what you built.

## The mental model

Two constants have been sitting in every `main.py` since Step 2:

```python
EOT_THRESHOLD = 0.7
EOT_TIMEOUT_MS = 5000
```

They're the reason turn-taking has felt reasonable all workshop. Reasonable is not the same as right for what *you're* building, and this is where you find out what they've been doing.

Turn detection is the hardest problem in voice, and it's an unwinnable trade. End the turn too early and you cut people off mid-thought. End it too late and every exchange has a dead pause in it. There's no setting that avoids both; there's only the setting that's right for your use case.

Flux scores every turn for end-of-turn confidence as the audio streams in. Both constants act on that score:

**`eot_threshold`** (0.5–0.9) is how much confidence Flux needs before calling the turn over. Raise it and the agent stops interrupting people who pause to think. Lower it and replies come faster, at the cost of the agent jumping in during those pauses.

**`eot_timeout_ms`** (500–60000) is the hard ceiling. End the turn after this much silence regardless of what the score says. It catches the case where someone trails off without a clean ending.

Both are optional. Omit them and you get Deepgram's server defaults — which is fine, right up to the first time someone tells you the agent talks over them.

## Do this

Optimization goes in one order: measure, change one thing, measure again. The TODOs follow it.

**TODO 8.1 — Turn on the latency report.** Uncomment the three lines in the `LatencyReport` branch.

`total_latency` measures end-of-utterance to first audio byte. It's the exact number your threshold changes move, and the only honest way to tell whether a change helped. Everything else is impression.

The report also carries `ttt_token_latency`, `ttt_text_latency`, `ttt_tool_latency`, `ttt_thinking_latency`, and `tts_latency`. Every field is optional — **absent, not zero**, when it doesn't apply. That's why the `None` check isn't decoration.

**TODO 8.2 — Move the dials.** Change `EOT_THRESHOLD` and `EOT_TIMEOUT_MS`, one at a time, and listen.

Values outside the valid ranges don't fail the handshake. They come back as a `Warning` — and you handle those now, since Step 6. If a value seems to do nothing, that branch will usually tell you why.

## Exercise: find your setting

Run the agent four times and hold the same short conversation each time. Write down what you notice.

| `EOT_THRESHOLD` | `EOT_TIMEOUT_MS` | What to listen for |
|---|---|---|
| `0.5` | `5000` | Snappy, and it interrupts you when you pause |
| `0.9` | `5000` | Patient to the point of feeling slow |
| `0.7` | `500` | Cuts you off on any real pause |
| `0.7` | `5000` | Where you started — the balance you've been using all workshop |

Watch `>> Latency:` alongside. The number moves, and it moves in the direction the setting predicts.

There's no correct answer here — it depends entirely on what you're building. A drive-through order taker wants low thresholds and fast turns. A therapy intake bot wants high thresholds and long silences. Pick the one that matches the agent you actually want.

> **Check yourself** — The agent keeps cutting you off when you pause to think. Which setting do you change, and in which direction?

## Verify

Latency prints once per turn:

```
[user] What's the tallest mountain in the world?
>> Agent thinking...
>> Agent started speaking
>> Latency: 0.94s
[assistant] Mount Everest, at about 29,032 feet.
```

And the two extreme settings sound obviously different from each other.

## Stuck?

**No `>> Latency:` line** — Either the lines are still commented out, or `total_latency` is absent on your turns. Print `message` directly in that branch to see what actually arrived.

**Changing the values does nothing** — Check the console for a `>> Agent warning`. A value outside its valid range is rejected and warned about rather than failing the handshake.

**Latency is high across the board** — `total_latency` includes the LLM. `gpt-4o-mini` is the fast option; if you switched to `gpt-4o` back in Step 6, this is the bill for it. Switch back and watch the number drop.

**Function calls make a turn slow** — Also in the number. `ttt_tool_latency` is your code, and Step 7 warned you it runs on the receive loop.

`steps/99-final/main.py` is this step, finished.

## Going further

Add `eager_eot_threshold=0.5` to the listen provider. Flux starts the LLM on a *probable* turn end and discards the work if you keep talking. Latency drops noticeably; your LLM call volume goes up, because some of those calls get thrown away. It must be less than or equal to `eot_threshold`.

That trade — spend compute to buy responsiveness — is one of the more interesting levers in production voice, and worth knowing before you need it.

---

You've built a complete voice agent and tuned it to feel the way you want: it listens on Flux, thinks with an LLM, speaks with Flux TTS, yields the floor when interrupted, calls your code when it needs something it can't know, and takes its turns on your terms.

**Next:** [Where to go from here](../99-final/README.md)
