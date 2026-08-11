# Step 6: Make it yours

**Goal:** Give the agent a job, a personality, and a voice.

**You'll learn**

- The two prompt instructions that separate a voice agent from a chatbot read aloud
- Where rejected settings go when they don't fail the handshake
- What swapping the LLM costs you in latency

## Start here

```bash
uv run steps/06-make-it-yours/main.py
```

Everything works: it hears you, answers you, and pauses when you talk over it. It's also a generic assistant with a stock voice, and it will stay that way until you change it.

This step has the least code in the workshop and the most to play with.

## The mental model

Three settings define the agent's character, and they're independent of each other:

**`prompt`:** the standing instructions the model sees ahead of every user turn. Personality, job, boundaries.

**`speak.provider.model`:** the voice. Purely how it sounds; it changes nothing about what the agent says.

**`greeting`:** the opening line, and the only thing the agent says before it knows anything about the user. It's doing all the work of setting expectations.

The prompt deserves the most attention, because writing prompts for *speech* differs from writing them for chat in two specific ways.

**Tell it that it's speaking.** LLMs default to writing. Without an explicit instruction you get markdown, bullet points, and asterisks read aloud, and it's genuinely jarring the first time you hear a TTS engine pronounce "asterisk asterisk important asterisk asterisk."

**Tell it to be brief.** A four-sentence answer that scans fine in a chat window feels interminable when you have to sit through it. Voice punishes verbosity in a way text doesn't.

Keep the prompt short for a second reason: every turn re-sends every token, and long prompts slow the first reply.

> **Check yourself:** Name the two prompt instructions that matter for speech but not for chat.

## Do this

**TODO 6.1: Give your agent a job.** Rewrite the prompt. Cover both rules above, then make it something specific: a barista taking an order, support for a product you know well, a dungeon master, a museum guide.

**TODO 6.2: Pick a voice.** Swap `flux-alexis-en` for another Flux voice. The full list lives in the [Deepgram TTS models documentation](https://developers.deepgram.com/docs/tts-models).

**TODO 6.2b: Write a new opening line.** Match it to the job you just assigned.

**TODO 6.3: Try a different brain.** `gpt-4o-mini` is fast and cheap, which matters more than raw capability when someone is waiting to hear a reply. Switch to `gpt-4o` and watch the latency readout on the right of the browser's activity line. You're paying for that capability in a currency your users feel directly. Step 8 is where that number becomes the whole point.

`temperature` controls variability: `0.0` for an agent that must say the same thing every time, `1.0` and up for a chatty one. Other providers work here too (Anthropic, Google, Groq, AWS Bedrock) via the matching `ThinkSettingsV1Provider_*` class. Note that you're switching models without an OpenAI account: Deepgram brokers that call. It doesn't broker all of them, and [Step 6b](../06b-bring-your-own-llm/LAB.md) is the optional detour into what changes when the model runs in your account instead.

**TODO 6.4: Surface warnings.** Add a `Warning` branch mirroring the `Error` branch above it.

Warnings are where rejected settings go. A misspelled voice or an out-of-range threshold arrives here rather than failing the handshake, so without this branch the agent silently ignores a bad setting and you're left wondering why nothing changed. It also makes Step 8's thresholds debuggable.

## Verify

Your agent greets you in character, in a different voice, and stays in role when you push at it. A deliberately misspelled voice model prints something like:

```
>> Agent warning: INVALID_VOICE - Unknown speak model 'flux-alexei-en'
```

Ask it something that would normally get a bulleted list ("what are the main types of coffee drinks?") and confirm you hear prose, not punctuation.

> **⏸ Pause: check in with the instructor**
> Good moment to go around the room. Personas are the most fun part of the workshop and hearing four different agents makes the prompt lesson land harder than any explanation.

## Stuck?

**It still reads markdown aloud.** The instruction has to be explicit. "Never use markdown, bullet points, or emoji" works; "be conversational" doesn't.

**It ignores the persona after a few turns.** Move the important constraints to the *end* of your prompt, and cut anything that isn't load-bearing.

**Answers got long again.** Larger models are more verbose by default. Re-state the brevity instruction, or go back to `gpt-4o-mini`.

**Voice didn't change and there's no warning.** Confirm you edited `speak`, not `listen`, and that TODO 6.4 is done.

**Noticeably slower after switching models.** Working as intended. Check the browser's latency readout and decide whether the quality is worth it.

`steps/07-function-calling/main.py` is this step, finished. It resets to the neutral prompt and voice, so everyone starts Step 7 from the same place regardless of the persona they chose. Carry yours forward if you'd rather.

## Going further

Give the agent a constraint it has to hold under pressure ("you only discuss coffee, and you politely redirect anything else"), then spend two minutes trying to talk it off-topic. Prompt injection resistance in a voice agent is the same problem as in a chat agent, except your attacker is talking out loud.

---

Your agent has a job and a voice. What it can't do yet is anything outside its own head.

**Next:** [Step 7: Function calling](../07-function-calling/LAB.md)
