"""Step 5 - Barge-in.

Runs exactly as Step 4 left it: a full two-way conversation.

BEFORE YOU WRITE ANY CODE, run this file and interrupt the agent mid-sentence.
Talk over it. It keeps going, cheerfully talking across you, while the console
prints ">> UserStartedSpeaking". That gap between what the server knows and what
your speaker is doing is the bug you are about to fix, and it is the difference
between a demo and something a person would willingly use.

Look for the "TODO (Step 5.1)" block below.

Press Ctrl+C to exit.
"""

import os
import threading
import time

import sounddevice as sd
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
                try:
                    speaker.write(message)
                except sd.PortAudioError as error:
                    # Dropping a chunk beats ending the call. This handler runs
                    # inside the SDK's receive loop, which wraps the whole loop
                    # in a single try/except, so any exception escaping here is
                    # reported as EventType.ERROR and closes the connection.
                    print(f">> Dropped audio chunk: {error}")
                return

            message_type = getattr(message, "type", "Unknown")

            if message_type == "SettingsApplied":
                print(">> Settings applied")
                settings_applied.set()
            elif message_type == "ConversationText":
                role = getattr(message, "role", "unknown")
                content = getattr(message, "content", "")
                print(f"[{role}] {content}")
            # ---- TODO (Step 5.1): Stop talking when the user starts -------
            # Add a branch here for "UserStartedSpeaking".
            #
            # What has already happened by the time this arrives: Flux detected
            # start-of-turn server-side and the agent stopped sending audio.
            # The problem is everything it *already* sent, which is sitting in
            # PortAudio's buffer and will keep playing over the user for as
            # long as it takes to drain -- easily a second or two.
            #
            # So clear the buffer:
            #
            #   speaker.abort()   # discard what is queued
            #   speaker.start()   # reopen for the next reply
            #
            # Use abort(), not stop(). stop() *drains* the buffer -- it plays
            # everything already queued before stopping, which is precisely the
            # behaviour you are trying to eliminate. This is the single most
            # common bug in a first voice agent, and it is nearly invisible in
            # code review because stop() looks like the more polite call.
            #
            # Wrap both in try/except sd.PortAudioError and print either way.
            # A failed barge-in should not end the conversation.
            #
            # Note there is no client-side voice activity detection anywhere in
            # this file. Flux does turn detection inside the model; the client's
            # entire obligation is reacting to this one message promptly.
            # ---------------------------------------------------------------
            elif message_type == "AgentThinking":
                print(">> Agent thinking...")
            elif message_type == "AgentStartedSpeaking":
                print(">> Agent started speaking")
            elif message_type == "AgentAudioDone":
                print(">> Agent finished speaking")
            elif message_type == "LatencyReport":
                # One report per turn, arriving right after the reply starts.
                # Printed, it buries the conversation -- Step 6 turns it on
                # once there is something to measure.
                pass
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
            stays a single non-blocking send. Nothing here inspects the audio --
            Flux decides where turns begin and end server-side.

            Args:
                indata: Captured PCM frames, BLOCK_SIZE of them. Copied with
                    bytes() because PortAudio reuses the underlying memory once
                    this callback returns.
                _frames: Number of frames in indata. Unused.
                _time_info: PortAudio timing information. Unused.
                _status: PortAudio status flags. Unused.
            """
            try:
                agent.send_media(bytes(indata))
            except Exception as error:
                # PortAudio runs this on its own thread, so a stray exception
                # would abort the stream and resurface out of microphone.stop()
                # during shutdown, burying the real cause. A dead socket has
                # nowhere left to send audio, so stop capturing on purpose.
                print(f">> Microphone stopped: {error}")
                raise sd.CallbackAbort from error

        microphone = sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            blocksize=BLOCK_SIZE,
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
