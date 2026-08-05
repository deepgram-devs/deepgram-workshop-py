"""Step 3 - Hear the agent.

Runs exactly as Step 2 left it: connects, applies settings, prints events.

The agent is already speaking. Run this file and watch the console -- after
">> Settings applied" you will see ">> AgentStartedSpeaking", and Flux TTS audio
is arriving on the socket right now. It is being thrown away, because there is
nowhere to play it.

This step gives it somewhere to go. By the end you will hear the greeting.

Look for the "TODO (Step 3.x)" blocks below.

Press Ctrl+C to exit.
"""

# ---- TODO (Step 3.1): Import the audio library ----------------------------
# Add this line to the imports below:
#
#   import sounddevice as sd
#
# It belongs at the top of the third-party group, just above "from deepgram
# import DeepgramClient" -- that group is sorted alphabetically, and ruff will
# tell you if it lands anywhere else.
#
# sounddevice ships PortAudio binaries inside its wheels for Linux, macOS, and
# Windows, so there is nothing to install at the system level. That is the
# whole reason this workshop uses it.
# ---------------------------------------------------------------------------

import os
import threading
import time

from deepgram import DeepgramClient
from deepgram.agent.v1.types import (
    AgentV1Settings,
    AgentV1SettingsAgent,
    AgentV1SettingsAgentListen,
    AgentV1SettingsAgentListenProvider_V2,
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

load_dotenv()

AgentMessage = str | bytes

SAMPLE_RATE = 24000 # Deepgram's recommended sample rate for voice agents. For telephony, 8000 is recommended.
CHANNELS = 1 # Deepgram's recommended channel count for voice agents. Mono is the most widely supported format across platforms and languages.
DTYPE = "int16" # Deepgram's recommended PCM format for voice agents. Raw 16-bit signed integer PCM is the most widely supported format across platforms and languages.
BLOCK_SIZE = SAMPLE_RATE * 80 // 1000 # 80 ms of audio per block, the chunk size Flux is tuned for. Smaller blocks add websocket overhead; larger ones delay turn detection.

SETTINGS = AgentV1Settings(
    audio=AgentV1SettingsAudio(
        input=AgentV1SettingsAudioInput(encoding="linear16", sample_rate=SAMPLE_RATE),
        output=AgentV1SettingsAudioOutput(encoding="linear16", sample_rate=SAMPLE_RATE),
    ),
    agent=AgentV1SettingsAgent(
        # Flux is Deepgram's conversational speech-to-text model, built for
        # voice agents. The "v2" provider version routes the agent to the v2
        # Listen backend (wss://api.deepgram.com/v2/listen), where the flux
        # models live. Turn detection is part of the model, so its thresholds
        # are configured here -- Step 6 turns those knobs.
        listen=AgentV1SettingsAgentListen(
            provider=AgentV1SettingsAgentListenProvider_V2(
                type="deepgram",
                model="flux-general-en", # Deepgram's general-purpose English voice agent model. Use flux-general-multi for auto-detection. See: https://developers.deepgram.com/docs/flux/language-prompting
            ),
        ),
        think=ThinkSettingsV1(
            provider=ThinkSettingsV1Provider_OpenAi(
                type="open_ai",
                model="gpt-4o-mini",
                temperature=0.7,
            ),
            # The prompt is prepended to every user turn before it reaches the
            # LLM. It is the agent's standing instructions -- personality, job,
            # and boundaries. Keep it short: every token here is re-sent on
            # every turn, and long prompts slow the first reply.
            prompt="You are a helpful AI assistant. Keep your responses brief.",
        ),
        # Flux TTS is Deepgram's streaming, turn-based voice engine built for
        # voice agents. The "flux-" model prefix routes the agent to the v2
        # Speak backend (wss://api.deepgram.com/v2/speak) automatically.
        speak=SpeakSettingsV1(
            provider=SpeakSettingsV1Provider_Deepgram(
                type="deepgram",
                model="flux-alexis-en",
            ),
        ),
        # The agent's first utterance, spoken as soon as settings are applied.
        # It is added to the conversation history, so the LLM knows it already
        # said this and will not repeat itself on the first real turn.
        greeting="Hello! I'm a Deepgram voice agent. What would you like to talk about?",
    ),
)


def main() -> None:
    """Open the agent connection and play the agent's audio until interrupted.

    Registers the event handlers, applies SETTINGS, and waits for the agent to
    acknowledge them. The agent discards media until the settings handshake
    completes, so the order matters.

    Raises:
        TimeoutError: If the agent does not acknowledge SETTINGS within ten
            seconds.
    """
    client = DeepgramClient(api_key=os.getenv("DEEPGRAM_API_KEY"))

    with client.agent.v1.connect() as agent:
        settings_applied = threading.Event()

        # ---- TODO (Step 3.2): Open the speaker ------------------------------
        # Create the output stream here, before the handlers below, and start
        # it. It has to exist before the first audio frame arrives, and with a
        # greeting configured that happens within milliseconds of
        # SettingsApplied.
        #
        #   speaker = sd.RawOutputStream(
        #       samplerate=SAMPLE_RATE,
        #       channels=CHANNELS,
        #       dtype=DTYPE,
        #   )
        #   speaker.start()
        #
        # "Raw" means the stream takes bytes rather than numpy arrays -- which
        # is exactly what arrives off the socket, so nothing needs converting.
        # The three constants match the output settings in SETTINGS above; if
        # they ever disagree, you get audio at the wrong speed and pitch, which
        # is a memorable way to learn this lesson.
        # ---------------------------------------------------------------------

        def on_message(message: AgentMessage) -> None:
            """Handle one inbound frame from the agent.

            Unrecognized message types fall through to a plain print so that new
            server events stay visible rather than being silently dropped.

            Args:
                message: Either raw bytes of Flux TTS audio, or a decoded model
                    whose "type" attribute names the event.
            """
            if isinstance(message, bytes):
                # ---- TODO (Step 3.3): Play it ---------------------------
                # This branch already catches every audio frame -- it just
                # drops them. Write them to the speaker instead:
                #
                #   try:
                #       speaker.write(message)
                #   except sd.PortAudioError as error:
                #       print(f">> Dropped audio chunk: {error}")
                #
                # Catch PortAudioError rather than letting it fly. This handler
                # runs inside the SDK's receive loop, which wraps the entire
                # loop in one try/except -- so any exception escaping here is
                # reported as EventType.ERROR and closes the connection.
                # Dropping one 80 ms chunk beats ending the call.
                # ---------------------------------------------------------
                return

            message_type = getattr(message, "type", "Unknown")

            if message_type == "SettingsApplied":
                print(">> Settings applied")
                settings_applied.set()
            elif message_type == "ConversationText":
                role = getattr(message, "role", "unknown")
                content = getattr(message, "content", "")
                print(f"[{role}] {content}")
            # ---- TODO (Step 3.4): Narrate the turn ----------------------
            # Right now every event you have not named prints as a bare
            # ">> SomeEventName" via the fallthrough at the bottom. Give the
            # interesting ones proper branches so the console reads like a
            # transcript of what the agent is doing:
            #
            #   elif message_type == "AgentThinking":
            #       print(">> Agent thinking...")
            #   elif message_type == "AgentStartedSpeaking":
            #       print(">> Agent started speaking")
            #   elif message_type == "AgentAudioDone":
            #       print(">> Agent finished speaking")
            #   elif message_type == "LatencyReport":
            #       pass
            #
            # LatencyReport gets an explicit `pass` rather than being left to
            # the fallthrough: it fires once per turn and would otherwise clutter
            # the transcript. Step 6 turns it into something useful.
            # -------------------------------------------------------------
            elif message_type == "Error":
                code = getattr(message, "code", "unknown")
                description = getattr(message, "description", "unknown error")
                print(f">> Agent error: {code} - {description}")
            else:
                print(f">> {message_type}")

        agent.on(EventType.OPEN, lambda _: print(">> Connection opened"))
        agent.on(EventType.MESSAGE, on_message)
        agent.on(EventType.CLOSE, lambda _: print(">> Connection closed"))
        agent.on(EventType.ERROR, lambda error: print(f">> Error: {error}"))

        listener = threading.Thread(target=agent.start_listening, daemon=True)
        listener.start()

        print("Sending agent settings...")
        agent.send_settings(SETTINGS)

        if not settings_applied.wait(10):
            raise TimeoutError("Timed out waiting for agent settings to apply.")

        # ---- TODO (Step 3.5): Release the device on the way out ------------
        # Add a finally clause to the try below so the speaker is closed even
        # after Ctrl+C:
        #
        #   finally:
        #       speaker.stop()
        #
        # Leaving PortAudio streams open is how you end up needing to restart
        # your terminal to get audio back.
        # ---------------------------------------------------------------------
        # Ten seconds, not forever: the agent expects a continuous media stream
        # and hangs up with CLIENT_MESSAGE_TIMEOUT after about fifteen seconds
        # of silence from us. Nothing sends audio until Step 4.
        print("\nListening to the greeting... (Step 4 opens the microphone)\n")
        try:
            time.sleep(10)
        except KeyboardInterrupt:
            print("\nShutting down...")


if __name__ == "__main__":
    main()
