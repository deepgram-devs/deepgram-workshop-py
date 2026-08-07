"""Step 1 - Setup check.

Nothing to write in this step. Run it, and it tells you whether this machine is
ready for the rest of the workshop.

It checks these, in the order they will bite you:

  1. The packages import.
  2. DEEPGRAM_API_KEY exists and Deepgram actually accepts it.
  3. DEEPGRAM_REGION names a real hosting location -- see web/region.py.
  4. The agent you are about to build actually starts there: this opens the
     same WebSocket Step 2 opens, with the same three models, and waits for
     the server to accept them.
  5. Your browser can reach the microphone at all -- secure context, and an
     AudioWorklet to run it in.
  6. The microphone hears you.
  7. The speaker makes noise.

The last three happen in a browser page this script serves, because that is
where the rest of the workshop's audio happens. Checking them anywhere else
would be checking something other than what you are about to use.

Audio problems are the single most common way a voice workshop loses twenty
minutes, and they are far easier to diagnose here than tangled up with a
WebSocket. The browser check is also what triggers the microphone permission
prompt.

Run it with:      uv run steps/01-setup/main.py
PortAudio path:   uv run steps/01-setup/main.py --local

The --local flag checks the system microphone and speaker through PortAudio
instead. Use it if you plan to run the later steps with --local.
"""

import os
import platform
import sys
import threading
import time

from deepgram.agent.v1.types import (
    AgentV1Settings,
    AgentV1SettingsAgent,
    AgentV1SettingsAgentContextListen,
    AgentV1SettingsAgentContextListenProvider_V2,
    AgentV1SettingsAudio,
    AgentV1SettingsAudioInput,
    AgentV1SettingsAudioOutput,
)
from deepgram.core.events import EventType
from deepgram.types.speak_settings_v1 import SpeakSettingsV1
from deepgram.types.speak_settings_v1provider import SpeakSettingsV1Provider_Deepgram
from deepgram.types.think_settings_v1 import ThinkSettingsV1
from deepgram.types.think_settings_v1provider import ThinkSettingsV1Provider_OpenAi
from dotenv import load_dotenv

from web import bridge, region

load_dotenv()

# WSL reports itself as Linux, but its audio needs a PulseAudio-to-ALSA bridge
# that native Linux does not. "microsoft" in the kernel release is the standard
# way to tell the two apart. Only --local cares: the browser path goes through
# Windows, not through WSL's audio stack, which is one of its quieter benefits.
IS_WSL = sys.platform == "linux" and "microsoft" in platform.uname().release.lower()

SAMPLE_RATE = 24000  # Matches the rate the agent uses from Step 2 onward.
CHANNELS = 1
DTYPE = "int16"
INT16_MAX = 32768.0

RECORD_SECONDS = 4
TONE_SECONDS = 1.0
TONE_HZ = 440.0
# Peak level (0.0-1.0) that counts as "the microphone is definitely working".
# Deliberately low: quiet built-in mics are normal and still work fine.
GOOD_PEAK = 0.02

PASS = "  OK  "
WARN = " WARN "
FAIL = " FAIL "

# The three models every step from Step 2 on configures. They are named here so
# this check exercises the pipeline you are about to build rather than some
# other agent -- scripts/verify_steps.py fails if they drift apart from Step 2's
# SETTINGS. Model availability is per-region and moves over time, so "does this
# key work" and "do these models run where I am connecting" are two questions.
LISTEN_MODEL = "flux-general-en"
THINK_MODEL = "gpt-4o-mini"
SPEAK_MODEL = "flux-alexis-en"

# How long to give the handshake, in seconds. Generous: it covers DNS, TLS, the
# WebSocket upgrade, and the server accepting three models, on conference wifi.
HANDSHAKE_TIMEOUT = 20.0


def audio_hint() -> None:
    """Print the audio fix most likely to apply on this platform.

    Only reached on the --local path. The browser path fails differently, and
    its page says what to do about each case.
    """
    if sys.platform == "darwin":
        print("         macOS: System Settings > Privacy & Security > Microphone,")
        print("         and enable your terminal or editor. Run this again after.")
    elif IS_WSL:
        print("         WSL routes audio through PulseAudio but PortAudio looks")
        print("         for ALSA. Bridge them:")
        print("           sudo apt install -y libasound2-plugins")
        print("           printf 'pcm.!default { type pulse }\\nctl.!default { type pulse }\\n' > ~/.asoundrc")
        print("         Or drop --local and use the browser, which needs none of this.")
    elif sys.platform == "linux":
        print("         Linux: install the PortAudio and ALSA userspace packages:")
        print("           sudo apt install -y libportaudio2 libasound2-plugins alsa-utils")
        print("         Or drop --local and use the browser, which needs none of this.")
    elif sys.platform == "win32":
        print("         Windows: Settings > Privacy & security > Microphone, and")
        print("         allow desktop apps to access it.")


def check_key() -> tuple[bool, str]:
    """Confirm DEEPGRAM_API_KEY is set and that Deepgram accepts it.

    Returns:
        Whether the key works, and a one-line explanation. The explanation is
        shown in the terminal and again on the browser page, so it is written
        to be read by someone who has not seen the other one.
    """
    key = os.getenv("DEEPGRAM_API_KEY")

    if not key:
        print(f"[{FAIL}] DEEPGRAM_API_KEY is not set.")
        print("         Copy .env.example to .env and paste your key into it:")
        print("           cp .env.example .env")
        print("         Get a free key at https://console.deepgram.com/signup?jump=keys")
        return False, "Not set. Copy .env.example to .env and paste your key into it."

    print(f"[{PASS}] DEEPGRAM_API_KEY found ({key[:4]}...{key[-4:]})")

    # A non-empty string is not the same as a working key. One cheap authorized
    # call now saves a confusing WebSocket failure in Step 2.
    #
    # Deliberately the global endpoint, whatever DEEPGRAM_REGION says: the
    # Management API is Deepgram's control plane and lives on api.deepgram.com
    # for every region. Your key is the same key everywhere, so this proves it
    # wherever your audio ends up going. check_region below covers the rest.
    try:
        projects = region.management_client(key).manage.v1.projects.list()
    except Exception as error:  # noqa: BLE001 -- any failure here means "unusable key"
        print(f"[{FAIL}] Deepgram rejected the key: {error}")
        print("         Check for a stray space or a truncated paste in .env.")
        return False, f"Deepgram rejected it: {error}. Check for a stray space or a truncated paste in .env."

    names = [p.name for p in (getattr(projects, "projects", None) or []) if p.name]
    where = f" (project: {names[0]})" if names else ""
    print(f"[{PASS}] Deepgram accepted the key{where}")
    return True, f"Accepted by Deepgram{where}"


def check_region() -> str | None:
    """Report which Deepgram hosting location this workshop will use.

    Almost everyone leaves DEEPGRAM_REGION alone and this is one quiet line. It
    earns its place in a room running against the EU or AU endpoint, where the
    address printed here is the first thing to check when nothing connects.

    Returns:
        The configured region, or None if DEEPGRAM_REGION names something that
        is not a Deepgram hosting location.
    """
    try:
        name = region.configured_region()
    except ValueError as error:
        print(f"[{FAIL}] {error}")
        print("         DEEPGRAM_REGION lives in .env at the repository root.")
        return None

    print(f"[{PASS}] Region: {region.describe(name)}")
    return name


def agent_settings() -> AgentV1Settings:
    """Describe the smallest agent that still proves the real one will start.

    The same three models and the same audio contract as Step 2, and nothing
    else: no prompt, no greeting, nothing that would make this a second place
    the workshop's agent is configured.

    Returns:
        Settings to hand to the agent socket.
    """
    return AgentV1Settings(
        audio=AgentV1SettingsAudio(
            input=AgentV1SettingsAudioInput(encoding="linear16", sample_rate=SAMPLE_RATE),
            output=AgentV1SettingsAudioOutput(encoding="linear16", sample_rate=SAMPLE_RATE),
        ),
        agent=AgentV1SettingsAgent(
            listen=AgentV1SettingsAgentContextListen(
                provider=AgentV1SettingsAgentContextListenProvider_V2(type="deepgram", model=LISTEN_MODEL),
            ),
            think=ThinkSettingsV1(provider=ThinkSettingsV1Provider_OpenAi(type="open_ai", model=THINK_MODEL)),
            speak=SpeakSettingsV1(provider=SpeakSettingsV1Provider_Deepgram(type="deepgram", model=SPEAK_MODEL)),
        ),
    )


def check_agent(name: str | None) -> bool:
    """Start the workshop's agent for real, and hang up once the server accepts it.

    The strongest check in this file, and the reason it is worth the four
    seconds: it is Step 2's handshake, run early. It proves the key is
    authorized for the Agent API, that this network can hold a WebSocket to the
    endpoint in use, and -- the part nothing else covers -- that all three
    models are actually served from the region you are connecting to. Model
    availability moves, and it is not the same everywhere.

    No audio is ever sent, so the connection is closed long before the agent's
    fifteen-second media timeout has anything to say about it.

    Args:
        name: The configured region, or None when it is unusable and there is
            nothing to connect to.

    Returns:
        Whether the agent accepted the settings.
    """
    if name is None:
        return False

    key = os.getenv("DEEPGRAM_API_KEY", "").strip()
    if not key:
        # check_key already said so, in more detail and with the fix.
        return False

    applied = threading.Event()
    # Populated from the listener thread; read after the wait below returns.
    failure: list[str] = []

    def on_message(message: object) -> None:
        """Watch for the handshake landing, or the server refusing it.

        Args:
            message: A decoded event model, or raw audio bytes.
        """
        message_type = getattr(message, "type", "")
        if message_type == "SettingsApplied":
            applied.set()
        elif message_type in {"Error", "Warning"}:
            code = getattr(message, "code", "unknown")
            description = getattr(message, "description", "")
            failure.append(f"{code} - {description}")
            applied.set()

    try:
        with region.deepgram_client(key, region=name).agent.v1.connect() as socket:
            socket.on(EventType.MESSAGE, on_message)
            threading.Thread(target=socket.start_listening, daemon=True).start()
            socket.send_settings(agent_settings())
            applied.wait(HANDSHAKE_TIMEOUT)
    except Exception as error:  # noqa: BLE001 -- report any connection problem, never crash
        print(f"[{FAIL}] Could not open the agent connection: {error}")
        # A key can pass the check above and still be refused here: the
        # Management API and the Agent API are different scopes, and a key
        # created with a narrow role has one and not the other.
        if "401" in str(error) or "403" in str(error):
            print("         Your key authenticates but is not allowed to use the Agent")
            print("         API. Create a new key in the Deepgram console with the")
            print("         default role rather than a restricted one.")
        else:
            print("         The key is accepted, so this is the network: it needs an")
            print("         outbound wss:// connection to")
            print(f"         {region.describe(name)}")
        return False

    if failure:
        print(f"[{FAIL}] The agent refused these settings: {failure[0]}")
        print(f"         Tried: {LISTEN_MODEL} + {THINK_MODEL} + {SPEAK_MODEL}")
        print("         Nothing is wrong with this machine. The model named above is")
        print("         not served from")
        print(f"           {region.describe(name)}")
        print("         Either set DEEPGRAM_REGION=global in .env, or replace that")
        print("         model in every step. For `speak`, aura-2-thalia-en is served")
        print("         everywhere, and Step 6 is where changing the voice is taught.")
        return False

    if not applied.is_set():
        print(f"[{FAIL}] The agent never acknowledged the settings ({HANDSHAKE_TIMEOUT:.0f}s).")
        print("         The connection opened, so this is usually a slow or filtered")
        print("         network. Try again; if it repeats, raise your hand.")
        return False

    print(f"[{PASS}] Agent started ({LISTEN_MODEL} + {THINK_MODEL} + {SPEAK_MODEL})")
    return True


def check_devices() -> bool:
    """Print the default input and output devices. The --local path only.

    Returns:
        True if both a default input and a default output device exist.
    """
    import sounddevice as sd

    try:
        default_input, default_output = sd.default.device
        devices = sd.query_devices()
    except Exception as error:  # noqa: BLE001 -- report any device problem, never crash
        print(f"[{FAIL}] Could not query audio devices: {error}")
        return False

    ok = True

    for label, index, channel_key in (
        ("Input ", default_input, "max_input_channels"),
        ("Output", default_output, "max_output_channels"),
    ):
        try:
            device = devices[index]
        except (IndexError, TypeError):
            device = None

        if device is None or device.get(channel_key, 0) < 1:
            print(f"[{FAIL}] {label}: no default device")
            ok = False
            continue

        print(f"[{PASS}] {label}: {device['name']} ({device[channel_key]} ch)")

    if not ok:
        print("         Pick a device in your OS sound settings, then re-run.")
        print("         Bluetooth headsets often need to be reconnected here.")
        audio_hint()

    return ok


def check_microphone() -> bool:
    """Capture a few seconds of audio and show a live level meter.

    The --local path only.

    Returns:
        True if the captured audio ever exceeded GOOD_PEAK.
    """
    import numpy as np
    import sounddevice as sd

    peak = 0.0

    def on_audio(indata: np.ndarray, _frames: int, _time_info: object, _status: object) -> None:
        """Track the loudest sample seen so far.

        Args:
            indata: Captured frames as int16.
            _frames: Frame count. Unused.
            _time_info: PortAudio timing. Unused.
            _status: PortAudio status flags. Unused.
        """
        nonlocal peak
        peak = max(peak, float(np.abs(indata).max()) / INT16_MAX)

    print(f"\n  Say something -- listening for {RECORD_SECONDS} seconds...")

    # The meter redraws itself with \r, which only makes sense on a terminal.
    # Piped or redirected, it would print one line per frame.
    live = sys.stdout.isatty()

    try:
        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            callback=on_audio,
        ):
            deadline = time.monotonic() + RECORD_SECONDS
            while time.monotonic() < deadline:
                if live:
                    filled = int(min(peak * 2.5, 1.0) * 30)
                    bar = "#" * filled + "." * (30 - filled)
                    print(f"\r  [{bar}] peak {peak:.2f}", end="", flush=True)
                time.sleep(0.05)
    except Exception as error:  # noqa: BLE001 -- report any device problem, never crash
        print(f"\n[{FAIL}] Microphone capture failed: {error}")
        audio_hint()
        return False

    if live:
        print()

    if peak < GOOD_PEAK:
        print(f"[{WARN}] Microphone opened but heard almost nothing (peak {peak:.3f}).")
        print("         Check you are not muted and the right input is selected.")
        audio_hint()
        return False

    print(f"[{PASS}] Microphone heard you (peak {peak:.2f})")
    return True


def check_speaker() -> bool:
    """Play a short tone so the user can confirm output works.

    The --local path only.

    Returns:
        True if playback completed without raising.
    """
    import numpy as np
    import sounddevice as sd

    samples = np.arange(int(SAMPLE_RATE * TONE_SECONDS))
    # Quarter amplitude -- loud enough to hear, quiet enough in headphones.
    wave = 0.25 * np.sin(2 * np.pi * TONE_HZ * samples / SAMPLE_RATE)
    # Fade the last 10% so the tone does not end on a click.
    fade = int(len(wave) * 0.1)
    wave[-fade:] *= np.linspace(1.0, 0.0, fade)

    print(f"\n  Playing a {TONE_HZ:.0f} Hz tone...")

    try:
        sd.play((wave * INT16_MAX).astype(np.int16), samplerate=SAMPLE_RATE)
        sd.wait()
    except Exception as error:  # noqa: BLE001 -- report any device problem, never crash
        print(f"[{FAIL}] Playback failed: {error}")
        audio_hint()
        return False

    print(f"[{PASS}] Speaker played a tone -- you should have heard it")
    return True


def check_local_audio() -> bool:
    """Run the PortAudio device, microphone, and speaker checks.

    Returns:
        True if every check passed.
    """
    try:
        import sounddevice  # noqa: F401 -- imported to prove it loads
    except OSError as error:
        print(f"[{FAIL}] sounddevice could not load PortAudio: {error}")
        audio_hint()
        return False

    if not check_devices():
        return False
    return check_microphone() and check_speaker()


def main() -> None:
    """Run every setup check and report whether this machine is ready."""
    print("Deepgram Voice Agent Workshop -- Step 1: Setup check")
    print("=" * 55)
    print(f"  Python {sys.version.split()[0]} on {sys.platform}\n")

    key_ok, key_detail = check_key()
    name = check_region()
    agent_ok = check_agent(name) if key_ok else False

    if "--local" in sys.argv:
        print()
        audio_ok = check_local_audio()
        print("\n" + "=" * 55)
        if key_ok and agent_ok and audio_ok:
            print("All checks passed. You are ready for Step 2:")
            print("  uv run steps/02-connect/main.py --local")
            return
        print("Some checks did not pass -- see the notes above.")
        print("If you are in a workshop, this is the moment to raise your hand.")
        # A failed setup check is a real failure, so exit non-zero. It also
        # means chaining this into the next step stops here rather than failing
        # more confusingly one step later.
        sys.exit(1)

    # The page checks the browser, not the network, so a refused handshake
    # would leave it reporting five cheerful green rows. Say so here, where it
    # happened, rather than letting it look like everything is fine.
    if not agent_ok:
        print("\n         The page below still checks your browser's audio, but the")
        print("         agent itself did not start -- see above. Step 2 will fail the")
        print("         same way until that is fixed.")

    # The browser half. run_check blocks until Ctrl+C, so nothing after it
    # runs -- the page reports its own verdict, which is where the remaining
    # three checks live.
    bridge.run_check(status={"key_ok": key_ok, "key_detail": key_detail})


if __name__ == "__main__":
    main()
