# Dev container

Everything the workshop needs is already installed: Python 3.13, `uv` 0.11.21, the locked dependencies, PortAudio, ALSA, and the Python and Ruff extensions. You supply a Deepgram API key and nothing else.

## Read this first: audio

**A container cannot reach your microphone or speaker unless the host hands them over, and only a Linux host can do that.** GitHub Codespaces has no audio hardware at all. This is a limitation of containers, not of the setup below.

So the dev container gets you a zero-install environment, not a zero-install voice agent:

| | Works in the container | Needs real hardware |
|---|---|---|
| Step 0 — Overview | ✅ read only | |
| Step 1 — Setup | ✅ key and device checks | ⚠️ mic and speaker checks fail |
| Step 2 — Connect | ✅ handshake, no audio yet | |
| Steps 3–6 | | ❌ streams live audio |
| Step 7 — Make it yours | ✅ edit prompt, persona, voice | ❌ hearing the result |
| Step 8 — Function calling | ✅ write and lint the handlers | ❌ triggering them by voice |
| `scripts/verify_steps.py` | ✅ | |

If you want to *hear* the agent — which is most of the point — run the workshop on your own machine, or share audio from a Linux host as described below.

## Getting started

Open the repository in a Codespace, or in VS Code with the Dev Containers extension (**Dev Containers: Reopen in Container**). On first create, Codespaces prompts you for `DEEPGRAM_API_KEY`; locally, paste your key into `.env` after the container comes up.

Then run any step:

```bash
uv run steps/02-connect/main.py
```

The virtual environment lives at `/opt/venv`, not `.venv`. That is deliberate: the workspace is a bind mount from your host, which may already hold a `.venv` built for macOS or Windows, and a Linux container cannot use it. `uv run` and the VS Code interpreter both point at `/opt/venv` already, so this only matters if you go looking for `.venv` and find nothing.

## Sharing audio from a Linux host

On a Linux desktop you can give the container your real devices. Uncomment the audio block at the bottom of [devcontainer.json](devcontainer.json) and rebuild:

```jsonc
"runArgs": ["--device=/dev/snd"],
"mounts": [
  "source=/run/user/1000/pulse,target=/run/user/1000/pulse,type=bind"
],
"containerEnv": {
  "PULSE_SERVER": "unix:/run/user/1000/pulse/native"
},
```

Check `id -u` on the host first — the paths assume UID 1000. If your host runs PipeWire, its PulseAudio compatibility socket lives in the same place and works unchanged.

Then confirm both directions:

```bash
uv run steps/01-setup/main.py
```

Leaving these lines uncommented on macOS, Windows, or Codespaces makes the container **fail to start**, because there is no `/dev/snd` to mount. That is why they ship commented out.

### PulseAudio over TCP

A host that exposes PulseAudio on TCP can reach the container over the network instead of a socket mount. On the host:

```bash
pactl load-module module-native-protocol-tcp port=4713 auth-ip-acl=127.0.0.1
```

Then set `"containerEnv": { "PULSE_SERVER": "tcp:host.docker.internal:4713" }`. This is the only route that works from Docker Desktop on macOS or Windows, and it requires you to be running a PulseAudio server on the host — which most macOS and Windows machines are not. Expect added latency, which matters in Step 6 where you measure turn-detection timing. Treat it as a workaround, not the supported path.

## Rebuilding

Dependency changes are picked up by `uv sync`. Changes to the `Dockerfile` or `devcontainer.json` need **Dev Containers: Rebuild Container**.
