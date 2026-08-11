# Step 1: Setup

**Goal:** Prove this machine can reach Deepgram and move audio in both directions, before getting too deep.

**You'll learn**

- Why `DEEPGRAM_API_KEY` is the only credential this workshop needs
- That a working key and a working agent are two different questions
- What a working microphone looks like from the browser's side of the glass
- The two browser capabilities everything after this depends on

## Why this step exists

Voice work fails in a specific, predictable order: the API key is wrong, the browser never got microphone permission, or you are serving the page from somewhere the browser refuses to trust with a microphone at all. Each of those produces a confusing error twenty minutes later, tangled up in WebSocket code where it looks like a Deepgram problem. Running the checks now turns all three into a one-line answer.

This step also triggers your browser's microphone permission prompt. The audio half of this check runs **in a browser page**, because that is where the rest of the workshop's audio runs. Be sure to approve the browser's request to access your microphone. If you need to change audio devices at any point, you may need to repeat this process by clicking the lock icon from the browser's address bar.

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

That key is the only credential you need. The agent you build uses OpenAI's `gpt-4o-mini` as its brain, but Deepgram brokers that call, so no OpenAI account, no second key, no second bill.

Deepgram applies **$200 in credit** to new accounts automatically. This workshop costs well under a dollar, so you'll have plenty left to keep building afterward.

`.env` also holds `DEEPGRAM_REGION`, which decides where Deepgram processes your audio: `global` by default, or `eu` or `au` for the endpoints that keep it inside those geographies. Leave it blank unless your instructor says otherwise. Your key works in every region, no code in this workshop names one, and moving between them is this single line.

> **Check yourself:** How many API keys does this workshop need, and why doesn't the LLM require its own?

> **⏸ Pause: check in with the instructor**
> Wait until everyone has a key in `.env` before moving on. This is the step where people get stuck, and it's much easier to fix now than in the middle of Step 2.

**3. Run the check.**

```bash
uv run steps/01-setup/main.py
```

It checks your key in the terminal, briefly starts the agent you're about to build, then opens a page. Press **Run the audio checks**, allow the microphone when your browser asks, speak when it tells you to, and listen for the tone. Ctrl+C in the terminal when you're done.

The check verifies the models are connecting over WebSockets without needing to send audio bytes.

## Verify

The terminal shows:

```
[  OK  ] DEEPGRAM_API_KEY found (84de...c2db)
[  OK  ] Deepgram accepted the key (project: Your Project)
[  OK  ] Region: global (wss://agent.deepgram.com/v1/agent/converse)
[  OK  ] Agent started (flux-general-en + gpt-4o-mini + flux-alexis-en)
```

and the page shows five green rows:

```
OK   Secure context      http://127.0.0.1:8000 is a secure context
OK   Audio support       AudioWorklet and getUserMedia are available
OK   Deepgram API key    Accepted by Deepgram (project: Your Project)
OK   Microphone          Heard you (peak 0.34).
OK   Speaker             Played a tone -- you should have heard it
```

Every row should read `OK`, and you heard a tone through your speakers. If there are any problems, start troubleshooting using the steps below.

## Stuck?

**`DEEPGRAM_API_KEY is not set`**. You created `.env` but the key landed in the wrong place, or the file is named `.env.txt`. The file belongs in the repository root, next to `pyproject.toml`.

**`Deepgram rejected the key`**. Almost always a truncated paste or a trailing space. Copy it again from the console.

**`DEEPGRAM_REGION=... is not a Deepgram hosting location`**. A typo in `.env`. The options are `global`, `eu`, and `au`; blank means `global`. The check refuses to guess, because a typo that quietly fell back to global would still work and would still be sending your audio to the wrong continent.

**`Could not open the agent connection`**. The key is fine and something is between you and Deepgram. Usually a proxy or firewall: this needs an outbound `wss://` connection to the address printed on the `Region` line above it. Corporate VPNs and guest wifi are the usual suspects; a phone hotspot is the fastest way to confirm it.

**`The agent refused these settings`**. Nothing is wrong with your machine. Deepgram doesn't serve one of the three models where you're connecting. The error names which one, and model availability differs by region. If you set `DEEPGRAM_REGION` yourself, set it back to blank. If your instructor set it, tell them: the fix is to change that one model in every step, and it's the same fix for everyone in the room.

**`Secure context` fails**. You opened the page on a LAN address like `192.168.1.5:8000`. Browsers only hand out microphone access on a secure context, and a bare IP is not one. Use `http://127.0.0.1:8000`, the address the terminal printed.

**`Permission denied`**. Your browser is blocking the microphone for this site. Click the icon at the left of the address bar, allow it, and press the button again. On macOS also check **System Settings → Privacy & Security → Microphone** and confirm your browser is enabled there.

**`Opened, but heard almost nothing`**. Two usual causes: you're muted, or the browser picked the wrong input. Change the input in your OS sound settings, reload the page, and try again.

**`Echo cancellation is off`**. Your browser did not grant it. Everything still works; wear headphones, and expect Step 5 to be noisier than it should be.

**`Browser gave 48000 Hz instead of 24000 Hz`**. Mostly iOS Safari, and the run still succeeds: the audio worklets resample instead. Quality drops a little and nothing else changes.

**Bluetooth headphones behaving strangely**. Many headsets expose a low-quality mono profile when their microphone activates, and some renegotiate the sample rate mid-session. Wired headphones are the reliable choice for the workshop, and they also spare you the speaker-feeding-microphone loop in Step 5.

**Nothing opens**. Some environments have no browser to open. The terminal prints the URL; open it yourself, or pass `--no-open` to stop it trying.

### If you plan to use `--local`

Every step also runs against the system microphone and speaker through PortAudio, with `--local`. If you intend to work that way, check it now:

```bash
uv run steps/01-setup/main.py --local
```

**`Could not query audio devices` on Linux**. Install ALSA's userspace pieces and the PulseAudio plugin:

```bash
sudo apt install -y libportaudio2 libasound2-plugins alsa-utils
```

**WSL** routes audio through PulseAudio, but PortAudio only looks for ALSA. Bridge the two:

```bash
sudo apt install -y libasound2-plugins
cat > ~/.asoundrc <<'EOF'
pcm.!default { type pulse }
ctl.!default { type pulse }
EOF
```

WSL audio used to be the single most common environment failure in this workshop. You can now sidestep it entirely: drop `--local` and the audio goes through your Windows browser instead, which needs none of the above.

## Going further

Open your browser's dev tools (F12) on the check page and watch the console while you run it. You'll see the sample rate the browser actually gave you. Then look at the Network tab: the browser fetches `worklets.js` and hands it to the audio thread, making it the only file in this workshop that does not run on the main thread.

---

With your environment confirmed working, you can open a connection to the Voice Agent API and start describing the agent you want to build.

**Next:** [Step 2: Connect](../02-connect/LAB.md)
