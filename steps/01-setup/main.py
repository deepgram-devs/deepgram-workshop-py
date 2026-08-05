"""Step 1 - Setup check.

Nothing to write in this step. Run it, and it tells you whether this machine is
ready for the rest of the workshop.

It checks four things, in the order they will bite you:

  1. The packages import.
  2. DEEPGRAM_API_KEY exists and Deepgram actually accepts it.
  3. There is a default input and output device.
  4. The microphone hears you and the speaker makes noise.

Audio problems are the single most common way a voice workshop loses twenty
minutes, and they are far easier to diagnose here than tangled up with a
WebSocket. On macOS this is also what triggers the microphone permission
prompt -- better now than mid-conversation in Step 4.

Run it with:  uv run steps/01-setup/main.py
"""

import os
import sys
import time

import numpy as np
import sounddevice as sd
from deepgram import DeepgramClient
from dotenv import load_dotenv

load_dotenv()

SAMPLE_RATE = 24000 # Matches the rate the agent uses from Step 2 onward.
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


def check_key() -> str | None:
    """Confirm DEEPGRAM_API_KEY is set and that Deepgram accepts it.

    Returns:
        The API key if Deepgram accepted it, otherwise None.
    """
    key = os.getenv("DEEPGRAM_API_KEY")

    if not key:
        print(f"[{FAIL}] DEEPGRAM_API_KEY is not set.")
        print("         Copy .env.example to .env and paste your key into it:")
        print("           cp .env.example .env")
        print("         Get a free key at https://console.deepgram.com/signup?jump=keys")
        return None

    print(f"[{PASS}] DEEPGRAM_API_KEY found ({key[:4]}...{key[-4:]})")

    # A non-empty string is not the same as a working key. One cheap authorized
    # call now saves a confusing WebSocket failure in Step 2.
    try:
        projects = DeepgramClient(api_key=key).manage.v1.projects.list()
    except Exception as error:  # noqa: BLE001 -- any failure here means "unusable key"
        print(f"[{FAIL}] Deepgram rejected the key: {error}")
        print("         Check for a stray space or a truncated paste in .env.")
        return None

    names = [p.name for p in (getattr(projects, "projects", None) or []) if p.name]
    where = f" (project: {names[0]})" if names else ""
    print(f"[{PASS}] Deepgram accepted the key{where}")
    return key


def check_devices() -> bool:
    """Print the default input and output devices.

    Returns:
        True if both a default input and a default output device exist.
    """
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

    return ok


def check_microphone() -> bool:
    """Capture a few seconds of audio and show a live level meter.

    Returns:
        True if the captured audio ever exceeded GOOD_PEAK.
    """
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
            samplerate=SAMPLE_RATE, channels=CHANNELS, dtype=DTYPE, callback=on_audio,
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
        if sys.platform == "darwin":
            print("         On macOS, check System Settings > Privacy & Security >")
            print("         Microphone and enable your terminal or editor.")
        return False

    if live:
        print()

    if peak < GOOD_PEAK:
        print(f"[{WARN}] Microphone opened but heard almost nothing (peak {peak:.3f}).")
        print("         Check you are not muted and the right input is selected.")
        if sys.platform == "darwin":
            print("         If macOS never prompted for microphone access, grant it in")
            print("         System Settings > Privacy & Security > Microphone.")
        return False

    print(f"[{PASS}] Microphone heard you (peak {peak:.2f})")
    return True


def check_speaker() -> bool:
    """Play a short tone so the user can confirm output works.

    Returns:
        True if playback completed without raising.
    """
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
        return False

    print(f"[{PASS}] Speaker played a tone -- you should have heard it")
    return True


def main() -> None:
    """Run every setup check and report whether this machine is ready."""
    print("Deepgram Voice Agent Workshop -- Step 1: Setup check")
    print("=" * 55)
    print(f"  Python {sys.version.split()[0]} on {sys.platform}\n")

    key_ok = check_key() is not None
    print()
    devices_ok = check_devices()

    microphone_ok = speaker_ok = False
    if devices_ok:
        microphone_ok = check_microphone()
        speaker_ok = check_speaker()

    print("\n" + "=" * 55)

    if key_ok and devices_ok and microphone_ok and speaker_ok:
        print("All checks passed. You are ready for Step 2:")
        print("  uv run steps/02-connect/main.py")
        return

    print("Some checks did not pass -- see the notes above.")
    print("If you are in a workshop, this is the moment to raise your hand.")
    # A failed setup check is a real failure, so exit non-zero. It also means
    # "uv run steps/01-setup/main.py && uv run steps/02-connect/main.py" stops
    # here rather than failing more confusingly one step later.
    sys.exit(1)


if __name__ == "__main__":
    main()
