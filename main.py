"""Bare-minimum Deepgram Voice Agent with live mic input and speaker output.

Captures audio from the default microphone, streams it to Deepgram's Voice Agent
WebSocket, and plays the agent's Flux TTS response back through the default speaker.
Cross-platform: sounddevice ships PortAudio binaries in its wheels for Linux,
macOS, and Windows, so no system-level audio install is required.

Press Ctrl+C to exit.
"""

import threading
import time
import os
from typing import Union

import sounddevice as sd
from deepgram import DeepgramClient
from deepgram.agent.v1.types import (
    AgentV1Settings,
    AgentV1SettingsAgent,
    AgentV1SettingsAgentListen,
    AgentV1SettingsAgentListenProvider_V1,
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

AgentMessage = Union[str, bytes]

SAMPLE_RATE = 24000
CHANNELS = 1
DTYPE = "int16"

SETTINGS = AgentV1Settings(
    audio=AgentV1SettingsAudio(
        input=AgentV1SettingsAudioInput(encoding="linear16", sample_rate=SAMPLE_RATE),
        output=AgentV1SettingsAudioOutput(encoding="linear16", sample_rate=SAMPLE_RATE),
    ),
    agent=AgentV1SettingsAgent(
        listen=AgentV1SettingsAgentListen(
            provider=AgentV1SettingsAgentListenProvider_V1(
                type="deepgram",
                model="nova-3",
            ),
        ),
        think=ThinkSettingsV1(
            provider=ThinkSettingsV1Provider_OpenAi(
                type="open_ai",
                model="gpt-4o-mini",
                temperature=0.7,
            ),
            prompt="You are a helpful AI assistant. Keep your responses brief.",
        ),
        # Flux TTS is Deepgram's streaming, turn-based voice engine built for
        # voice agents. The "flux-" model prefix routes the agent to the v2
        # Speak backend (wss://api.deepgram.com/v2/speak) automatically -- Aura
        # model names are not valid there, and flux names are not valid on v1.
        speak=SpeakSettingsV1(
            provider=SpeakSettingsV1Provider_Deepgram(
                type="deepgram",
                model="flux-alexis-en",
            ),
        ),
        greeting="Hello! I'm a Deepgram voice agent. What would you like to talk about?",
    ),
)


def main() -> None:
    """Open the agent connection and stream audio until interrupted.

    Starts the speaker, registers the event handlers, then applies SETTINGS and
    waits for the agent to acknowledge them before opening the microphone. The
    agent discards media until the settings handshake completes, so the order
    matters. Both audio streams are stopped on the way out, including after Ctrl+C.

    Raises:
        TimeoutError: If the agent does not acknowledge SETTINGS within ten
            seconds.
    """
    client = DeepgramClient(api_key=os.getenv("DEEPGRAM_API_KEY"))

    with client.agent.v1.connect() as agent:
        settings_applied = threading.Event()
        speaker = sd.RawOutputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
        )
        speaker.start()

        def on_message(message: AgentMessage) -> None:
            """Handle one inbound frame from the agent.

            Unrecognized message types fall through to a plain print so that new
            server events stay visible rather than being silently dropped.

            Args:
                message: Either raw bytes of Flux TTS audio, which are written
                    straight to the speaker, or a decoded model whose "type"
                    attribute names the event.
            """
            if isinstance(message, bytes):
                speaker.write(message)
                return

            message_type = getattr(message, "type", "Unknown")

            if message_type == "SettingsApplied":
                print(">> Settings applied")
                settings_applied.set()
            elif message_type == "ConversationText":
                role = getattr(message, "role", "unknown")
                content = getattr(message, "content", "")
                print(f"[{role}] {content}")
            elif message_type == "UserStartedSpeaking":
                print(">> User started speaking")
            elif message_type == "AgentThinking":
                print(">> Agent thinking...")
            elif message_type == "AgentStartedSpeaking":
                print(">> Agent started speaking")
            elif message_type == "AgentAudioDone":
                print(">> Agent finished speaking")
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

        def microphone_callback(
            indata: memoryview, _frames: int, _time_info: object, _status: object,
        ) -> None:
            """Forward one captured block of microphone audio to the agent.

            PortAudio invokes this on its own high-priority thread, so the body
            stays a single non-blocking send.

            Args:
                indata: Captured PCM frames. Copied with bytes() because
                    PortAudio reuses the underlying memory once this callback
                    returns.
                _frames: Number of frames in indata. Unused.
                _time_info: PortAudio timing information. Unused.
                _status: PortAudio status flags. Unused.
            """
            agent.send_media(bytes(indata))

        microphone = sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            callback=microphone_callback,
        )
        microphone.start()

        print("\nListening... press Ctrl+C to exit.\n")
        try:
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            microphone.stop()
            speaker.stop()


if __name__ == "__main__":
    main()
