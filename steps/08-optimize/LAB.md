# Step 6 — Tune turn detection

**Goal:** Take control of when the agent decides you've finished talking, and measure what it costs.

**You'll learn**

- What `eot_threshold` and `eot_timeout_ms` actually trade against each other
- How to read `LatencyReport` and which number matters
- Why `eager_eot_threshold` buys latency with LLM calls

## Start here

```bash
uv run steps/06-tune-turns/main.py
```

You have a complete, interruptible voice agent running on Flux's default turn-detection settings. This step is mostly dials rather than code — and it's the step that decides whether people enjoy talking to what you built.

## The mental model

Turn detection is the hardest problem in voice, and it's an unwinnable trade. End the turn too early and you cut people off mid-thought. End it too late and every exchange has a dead pause in it. There's no setting that avoids both; there's only the setting that's right for your use case.

Flux scores every turn for end-of-turn confidence as the audio streams in. Two settings act on that score:

**`eot_threshold`** (0.5–0.9) is how much confidence Flux needs before calling the turn over. Raise it and the agent stops interrupting people who pause to think. Lower it and replies come faster, at the cost of the agent jumping in during those pauses.

**`eot_timeout_ms`** (500–60000) is the hard ceiling. End the turn after this much silence regardless of what the score says. It catches the case where someone trails off without a clean ending.

Both are optional. Omitting them — as this file does right now — uses the server defaults, which is why Step 5 already worked.

## Do this

**TODO 6.1 — Add the constants.** `EOT_THRESHOLD = 0.7` and `EOT_TIMEOUT_MS = 5000`, at module level with the other configuration.

**TODO 6.2 — Wire them into the listen provider.** Pass both into `AgentV1SettingsAgentContextListenProvider_V2`.

Values outside the valid ranges don't fail the handshake. They come back as a `Warning` message, which nothing handles yet — Step 7 adds that branch. If a value seems to do nothing, that's usually why.

**TODO 6.3 — Turn on the latency report.** Uncomment the three lines in the `LatencyReport` branch.

`total_latency` measures end-of-utterance to first audio byte. It's the exact number your threshold changes move, and the only honest way to tell whether a change helped. Everything else is impression.

The report also carries `ttt_token_latency`, `ttt_text_latency`, `ttt_tool_latency`, `ttt_thinking_latency`, and `tts_latency`. Every field is optional — **absent, not zero**, when it doesn't apply. That's why the `None` check isn't decoration.

## Exercise: find your setting

Run the agent four times and hold the same short conversation each time. Write down what you notice.

| `EOT_THRESHOLD` | `EOT_TIMEOUT_MS` | What to listen for |
|---|---|---|
| `0.5` | `5000` | Snappy, and it interrupts you when you pause |
| `0.9` | `5000` | Patient to the point of feeling slow |
| `0.7` | `500` | Cuts you off on any real pause |
| `0.7` | `5000` | The default balance |

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

**Changing the values does nothing** — You added the constants but didn't pass them into the provider (TODO 6.2), or a value falls outside the valid range and came back as a `Warning` you can't see yet. Step 7 fixes the visibility.

**Latency is high across the board** — `total_latency` includes the LLM. `gpt-4o-mini` is the fast option; you'll see the difference immediately if you switch to a larger model in Step 7.

`steps/07-make-it-yours/main.py` is this step, finished.

## Going further

Add `eager_eot_threshold=0.5` to the listen provider. Flux starts the LLM on a *probable* turn end and discards the work if you keep talking. Latency drops noticeably; your LLM call volume goes up, because some of those calls get thrown away. It must be less than or equal to `eot_threshold`.

That trade — spend compute to buy responsiveness — is one of the more interesting levers in production voice, and worth knowing before you need it.

---

The turn-taking feels right. Now make the agent sound like something other than a demo.

**Next:** [Step 7 — Make it yours](../07-make-it-yours/LAB.md)
