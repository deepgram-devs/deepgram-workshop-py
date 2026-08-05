# Step 1 — Setup

**Goal:** Prove this machine can reach Deepgram and move audio in both directions, before any of it matters.

**You'll learn**

- Which audio devices your code will actually use, and how to change them
- Why `DEEPGRAM_API_KEY` is the only credential this workshop needs
- What a working microphone looks like from Python's side of the glass

## Why this step exists

Voice work fails in a specific, predictable order: the key is wrong, the wrong microphone is selected, or the OS never granted permission. Each of those produces a confusing error twenty minutes later, tangled up in WebSocket code where it looks like a Deepgram problem. Running the checks now turns all three into a one-line answer.

On macOS, this step also triggers the microphone permission prompt. Far better to see that dialog now than halfway through a conversation in Step 4.

## Do this

**1. Install the dependencies.** From the repository root:

```bash
uv sync
```

One virtual environment serves every step in this workshop. You run this once.

**2. Create your `.env` file.**

```bash
cp .env.example .env
```

Open `.env` and paste in your Deepgram API key. Grab a free one at [console.deepgram.com](https://console.deepgram.com/signup?jump=keys) if you don't have it yet.

That key is the only credential you need. The agent you build uses OpenAI's `gpt-4o-mini` as its brain, but Deepgram brokers that call — so no OpenAI account, no second key, no second bill.

**3. Run the check.**

```bash
uv run steps/01-setup/main.py
```

Speak when it asks you to, and listen for the tone.

## Verify

A clean run looks like this:

```
[  OK  ] DEEPGRAM_API_KEY found (84de...c2db)
[  OK  ] Deepgram accepted the key (project: Your Project)
[  OK  ] Input : MacBook Pro Microphone (1 ch)
[  OK  ] Output: MacBook Pro Speakers (2 ch)
[  OK  ] Microphone heard you (peak 0.34)
[  OK  ] Speaker played a tone -- you should have heard it

All checks passed. You are ready for Step 2:
```

Every line reads `OK`, and you heard the tone. Anything else, work through the fixes below.

## Stuck?

**`DEEPGRAM_API_KEY is not set`** — You created `.env` but the key landed in the wrong place, or the file is named `.env.txt`. The file belongs in the repository root, next to `pyproject.toml`.

**`Deepgram rejected the key`** — Almost always a truncated paste or a trailing space. Copy it again from the console.

**`Microphone opened but heard almost nothing`** — Three usual causes, in order of likelihood: you're muted, the wrong input device is selected, or macOS never granted microphone access. Check **System Settings → Privacy & Security → Microphone** and enable your terminal or editor, then re-run.

**Bluetooth headphones behaving strangely** — Many headsets expose a low-quality mono profile when their microphone activates. Disconnect and reconnect the headset, or use wired headphones for the workshop. Wired headphones also spare you the speaker-feeding-microphone loop in Step 5.

**Wrong device selected entirely** — `sounddevice` follows your operating system's default. Change the default in your OS sound settings and re-run; there's nothing to edit in the code.

## Going further

Run `uv run python -c "import sounddevice; print(sounddevice.query_devices())"` to see every device on your machine, not just the defaults. The index in that list is what you'd pass as `device=` to any `sounddevice` stream if you ever need to override the default explicitly.

---

With your environment confirmed working, you can open a connection to the Voice Agent API and start describing the agent you want to build.

**Next:** [Step 2 — Connect](../02-connect/LAB.md)
