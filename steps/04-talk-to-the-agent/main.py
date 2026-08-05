"""Step 4 - Talk to the agent.

Runs exactly as Step 3 left it: connects, applies settings, and plays the
greeting. Then it goes quiet, because nothing is sending it any audio.

This step closes the loop. You will capture microphone audio and stream it to
the agent, and by the end of it you will be having an actual conversation.

Look for the "TODO (Step 4.x)" blocks below.

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

        # ---- TODO (Step 4.1): Capture the microphone ----------------------
        # Everything below the settings handshake is new in this step. Note
        # *where* it goes: the agent discards media until SettingsApplied
        # arrives, so opening the microphone any earlier throws away your first
        # words. That is why the wait() above is not decorative.
        #
        # Write a callback PortAudio can hand blocks of captured audio to:
        #
        #   def microphone_callback(
        #       indata: memoryview, _frames: int, _time_info: object, _status: object,
        #   ) -> None:
        #       try:
        #           agent.send_media(bytes(indata))
        #       except Exception as error:
        #           print(f">> Microphone stopped: {error}")
        #           raise sd.CallbackAbort from error
        #
        # Three things in that tiny body are load-bearing:
        #
        #   * bytes(indata) *copies*. PortAudio reuses the underlying memory as
        #     soon as this returns, so passing the buffer along unmodified
        #     hands the socket a view of audio that is about to be overwritten.
        #
        #   * The body is one non-blocking send and nothing else. PortAudio
        #     calls this on a high-priority realtime thread on a strict
        #     schedule; anything slow here shows up as dropouts and glitches.
        #
        #   * sd.CallbackAbort on failure. A stray exception would kill the
        #     stream and then resurface out of microphone.stop() during
        #     shutdown, burying the real cause. A dead socket has nowhere left
        #     to send audio, so stop capturing deliberately.
        #
        # Note what is *not* here: no voice activity detection, no silence
        # trimming, no buffering. Flux decides where turns begin and end
        # server-side. Your job is to keep the pipe full.
        # -------------------------------------------------------------------

        # ---- TODO (Step 4.2): Open the input stream -----------------------
        # Mirror the speaker above, plus a block size and the callback:
        #
        #   microphone = sd.RawInputStream(
        #       samplerate=SAMPLE_RATE,
        #       channels=CHANNELS,
        #       dtype=DTYPE,
        #       blocksize=BLOCK_SIZE,
        #       callback=microphone_callback,
        #   )
        #   microphone.start()
        #
        # BLOCK_SIZE is 80 ms (see the constant at the top). It is the chunk
        # size Flux is tuned for: smaller blocks pay websocket overhead per
        # chunk, larger ones delay turn detection because Flux cannot score an
        # end-of-turn until the block containing it arrives.
        # -------------------------------------------------------------------

        # ---- TODO (Step 4.3): Run until interrupted -----------------------
        # Replace the sleep below with a real run loop, so the program stays up
        # for a conversation instead of a fixed ten seconds:
        #
        #   print("\nListening... press Ctrl+C to exit.\n")
        #   try:
        #       while True:
        #           time.sleep(0.1)
        #   except KeyboardInterrupt:
        #       print("\nShutting down...")
        #   finally:
        #       microphone.stop()
        #       speaker.stop()
        #
        # The main thread does nothing but idle -- every interesting thing
        # happens on the listener thread (inbound) and PortAudio's threads
        # (outbound). Add microphone.stop() to the finally so both devices are
        # released on the way out, including after Ctrl+C.
        #
        # An unbounded loop is safe here only *because* the microphone is now
        # streaming. The ten-second cap below exists because the agent hangs up
        # with CLIENT_MESSAGE_TIMEOUT after about fifteen seconds of receiving
        # no media -- once you are sending audio continuously, that never fires.
        # -------------------------------------------------------------------
        print("\nListening to the greeting... (Step 4 opens the microphone)\n")
        try:
            time.sleep(10)
        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            speaker.stop()


if __name__ == "__main__":
    main()
