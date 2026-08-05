"""Deepgram Voice Agent with live mic input, speaker output, and function calling.

This is the finished workshop project -- the end state of Step 8.

Captures audio from the default microphone, streams it to Deepgram's Voice Agent
WebSocket, and plays the agent's Flux TTS response back through the default speaker.
Cross-platform: sounddevice ships PortAudio binaries in its wheels for Linux,
macOS, and Windows, so no system-level audio install is required.

Speech-to-text runs on Flux, Deepgram's conversational model, which detects turn
boundaries inside the model. The client does no voice activity detection of its
own: the agent emits UserStartedSpeaking at start-of-turn and sends the
transcript to the LLM at end-of-turn. The client's one obligation is prompt
barge-in -- see the UserStartedSpeaking branch below.

Press Ctrl+C to exit.
"""

import json
import os
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import sounddevice as sd
from deepgram import DeepgramClient
from deepgram.agent.v1.types import (
    AgentV1SendFunctionCallResponse,
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
from deepgram.types.think_settings_v1functions_item import ThinkSettingsV1FunctionsItem
from deepgram.types.think_settings_v1provider import ThinkSettingsV1Provider_OpenAi
from dotenv import load_dotenv

load_dotenv()

AgentMessage = str | bytes

SAMPLE_RATE = 24000 # Deepgram's recommended sample rate for voice agents. For telephony, 8000 is recommended.
CHANNELS = 1 # Deepgram's recommended channel count for voice agents. Mono is the most widely supported format across platforms and languages.
DTYPE = "int16" # Deepgram's recommended PCM format for voice agents. Raw 16-bit signed integer PCM is the most widely supported format across platforms and languages.
BLOCK_SIZE = SAMPLE_RATE * 80 // 1000 # 80 ms of audio per block, the chunk size Flux is tuned for. Smaller blocks add websocket overhead; larger ones delay turn detection.

# Flux's turn detection knobs. Every turn gets an end-of-turn confidence score;
# these decide how much confidence is enough and how long silence may run.
EOT_THRESHOLD = 0.7 # Valid 0.5-0.9. Raise it to stop the agent cutting people off mid-thought, lower it for snappier replies at the cost of false turn ends.
EOT_TIMEOUT_MS = 5000 # Valid 500-60000. Hard ceiling: end the turn after this much silence no matter what the score says.
# Also available: eager_eot_threshold (0.3-0.9, off by default, must be <=
# EOT_THRESHOLD). It starts the LLM on a probable turn end and discards the work
# if the user keeps talking -- lower latency, more LLM calls.


def get_current_time(timezone: str = "UTC") -> str:
    """Return the current date and time in the named IANA timezone.

    The agent reads the return value aloud, so it is phrased as a sentence
    rather than a data structure.

    Args:
        timezone: IANA timezone name, for example "America/New_York". Falls
            back to UTC when the name is not recognized -- the LLM invents
            plausible-but-wrong timezone strings often enough that raising
            here would end otherwise fine conversations.

    Returns:
        A sentence describing the current local time in that timezone.
    """
    try:
        zone = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        timezone, zone = "UTC", ZoneInfo("UTC")

    now = datetime.now(zone)
    # strftime's %-I (no leading zero) is a glibc/BSD extension that fails on
    # Windows, so strip the zero by hand instead.
    clock = now.strftime("%I:%M %p").lstrip("0")
    return f"It is {clock} on {now.strftime('%A, %B %d')} in {timezone}."


# Maps the function names advertised in FUNCTIONS to the Python that runs them.
FUNCTION_HANDLERS = {
    "get_current_time": get_current_time,
}

# What the agent is told it can call. This is advertising only: the LLM decides
# *whether* to call, this client decides *what happens* when it does. Leaving
# "endpoint" unset marks a function client-side, which is what makes Deepgram
# send a FunctionCallRequest down the socket and wait for our
# FunctionCallResponse rather than calling an HTTP endpoint itself.
FUNCTIONS = [
    ThinkSettingsV1FunctionsItem(
        name="get_current_time",
        description=(
            "Get the current date and time in a given IANA timezone. Use this "
            "whenever the user asks what time it is or what today's date is."
        ),
        # A JSON Schema object, exactly as the LLM's tool-calling API expects.
        parameters={
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "description": (
                        "IANA timezone name, for example America/New_York or "
                        "Europe/London. Ask the user if you do not know it."
                    ),
                },
            },
            "required": ["timezone"],
        },
    ),
]

SETTINGS = AgentV1Settings(
    audio=AgentV1SettingsAudio(
        input=AgentV1SettingsAudioInput(encoding="linear16", sample_rate=SAMPLE_RATE),
        output=AgentV1SettingsAudioOutput(encoding="linear16", sample_rate=SAMPLE_RATE),
    ),
    agent=AgentV1SettingsAgent(
        # Flux is Deepgram's conversational speech-to-text model, built for
        # voice agents. The "v2" provider version routes the agent to the v2
        # Listen backend (wss://api.deepgram.com/v2/listen), where the flux
        # models live. Turn detection is part of the model, so the thresholds
        # are configured here.
        listen=AgentV1SettingsAgentListen(
            provider=AgentV1SettingsAgentListenProvider_V2(
                type="deepgram",
                model="flux-general-en", # Deepgram's general-purpose English voice agent model. Use flux-general-multi for auto-detection. See: https://developers.deepgram.com/docs/flux/language-prompting
                eot_threshold=EOT_THRESHOLD, # Valid 0.5-0.9. Raise it to stop the agent cutting people off mid-thought, lower it for snappier replies at the cost of false turn ends.
                eot_timeout_ms=EOT_TIMEOUT_MS, # Valid 500-60000. Hard ceiling: end the turn after this much silence no matter what the score says.
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
            prompt=(
                "You are a helpful AI assistant. Keep your responses brief. "
                "You are speaking out loud, so never use markdown, bullet "
                "points, or emoji."
            ),
            functions=FUNCTIONS,
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


def handle_function_call(agent: object, message: object) -> None:
    """Run every client-side function the agent asked for and return the results.

    The agent is mid-turn and blocked on these responses, so failures are
    reported back as the function's result rather than raised. A raised
    exception would escape into the SDK's receive loop, surface as
    EventType.ERROR, and drop the call.

    This runs on the SDK's receive loop thread, which is also the thread
    delivering audio. A slow function here stalls playback for everyone. Keep
    handlers fast, or hand the work to a thread and reply once it finishes.

    Args:
        agent: The connected agent socket, used to send each response.
        message: A FunctionCallRequest, whose "functions" attribute lists the
            calls to make. Each carries an id, a name, and "arguments" as a
            JSON string.
    """
    for call in getattr(message, "functions", []):
        name = getattr(call, "name", "")
        arguments = getattr(call, "arguments", "") or "{}"
        print(f">> Function call: {name}({arguments})")

        handler = FUNCTION_HANDLERS.get(name)
        if handler is None:
            content = f"No function named '{name}' is available."
        else:
            try:
                content = handler(**json.loads(arguments))
            except Exception as error:  # noqa: BLE001 -- see the docstring above
                content = f"{name} failed: {error}"

        print(f">> Function result: {content}")
        agent.send_function_call_response(
            AgentV1SendFunctionCallResponse(
                id=getattr(call, "id", None),
                name=name,
                content=content,
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
            elif message_type == "UserStartedSpeaking":
                # Flux detected start-of-turn, so the agent has stopped sending
                # audio -- but whatever it already sent is still queued in
                # PortAudio and would keep talking over the user. abort()
                # discards the queue (stop() would drain it, defeating the
                # point), then the stream is restarted for the next reply.
                try:
                    speaker.abort()
                    speaker.start()
                    print(">> User started speaking (barge-in: playback cleared)")
                except sd.PortAudioError as error:
                    print(f">> User started speaking (barge-in failed: {error})")
            elif message_type == "AgentThinking":
                print(">> Agent thinking...")
            elif message_type == "AgentStartedSpeaking":
                print(">> Agent started speaking")
            elif message_type == "AgentAudioDone":
                print(">> Agent finished speaking")
            elif message_type == "FunctionCallRequest":
                handle_function_call(agent, message)
            elif message_type == "LatencyReport":
                # One report per turn, arriving right after the reply starts.
                # total_latency is end-of-utterance to first audio byte -- the
                # number the turn-detection knobs above move. Also carries
                # ttt_token_latency, ttt_text_latency, ttt_tool_latency,
                # ttt_thinking_latency, and tts_latency. Every field is
                # optional -- absent, not zero, when it doesn't apply.
                total = getattr(message, "total_latency", None)
                if total is not None:
                    print(f">> Latency: {total:.2f}s")
            elif message_type == "Error":
                code = getattr(message, "code", "unknown")
                description = getattr(message, "description", "unknown error")
                print(f">> Agent error: {code} - {description}")
            elif message_type == "Warning":
                # Non-fatal, and the place a rejected setting shows up -- a bad
                # voice name or a threshold outside its valid range warns here
                # rather than failing the handshake.
                code = getattr(message, "code", "unknown")
                description = getattr(message, "description", "unknown warning")
                print(f">> Agent warning: {code} - {description}")
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
