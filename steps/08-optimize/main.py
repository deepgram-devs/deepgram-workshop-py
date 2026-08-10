"""Step 8 - Optimization.

Runs exactly as Step 7 left it: a complete voice agent that listens on Flux,
holds a conversation, yields the floor when interrupted, and calls your Python.

Nothing is missing. What is left is how it *feels*, and that comes down to two
numbers that have been sitting in this file since Step 2 -- EOT_THRESHOLD and
EOT_TIMEOUT_MS, which decide when Flux calls your turn over. They are set to a
balanced default. Balanced is not the same as right for what you are building.

This step is dials rather than architecture, and it goes in the order any
optimization goes: measure first, then move something, then measure again.

Look for the "TODO (Step 8.x)" blocks below. Inside them, "#:" marks the
instructions and everything else is code, commented out at the indentation it
belongs at: select those lines and press Cmd+/ (Ctrl+/ on Windows and Linux) to
uncomment them where they sit.

Run it with:  uv run steps/08-optimize/main.py
"""

import json
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from deepgram.agent.v1.types import (
    AgentV1SendFunctionCallResponse,
    AgentV1Settings,
    AgentV1SettingsAgent,
    AgentV1SettingsAgentContextListen,
    AgentV1SettingsAgentContextListenProvider_V2,
    AgentV1SettingsAudio,
    AgentV1SettingsAudioInput,
    AgentV1SettingsAudioOutput,
)
from deepgram.types.speak_settings_v1 import SpeakSettingsV1
from deepgram.types.speak_settings_v1provider import SpeakSettingsV1Provider_Deepgram
from deepgram.types.think_settings_v1 import ThinkSettingsV1
from deepgram.types.think_settings_v1functions_item import ThinkSettingsV1FunctionsItem
from deepgram.types.think_settings_v1provider import ThinkSettingsV1Provider_OpenAi
from dotenv import load_dotenv

from web import AgentHandle, Player, bridge

load_dotenv()

SAMPLE_RATE = 24000  # Deepgram's recommended sample rate for voice agents. For telephony, 8000 is recommended.
# Audio is mono 16-bit signed PCM in both directions -- the most widely
# supported format across platforms and languages. The browser sends it in
# 80 ms chunks, the size Flux's turn detection is tuned for: smaller chunks add
# websocket overhead, larger ones delay turn detection. web/bridge.py derives
# that chunk size from SAMPLE_RATE, so this constant is the only place to change
# it.

#: ---- TODO (Step 8.2): Move the dials -------------------------------------
#: Flux scores every turn for end-of-turn confidence as the audio streams in.
#: These two constants act on that score, and they trade against each other:
#: end a turn too early and you cut people off mid-thought, too late and every
#: exchange carries a dead pause. There is no setting that avoids both.
#:
#: Once TODO 8.1 is printing a number, run the four rows in the LAB's table --
#: 0.5/5000, 0.9/5000, 0.7/500, then back to 0.7/5000 -- holding the same short
#: conversation each time. Listen, and watch ">> Latency:" alongside.
#:
#: A value outside its valid range does not fail the handshake. It comes back as
#: a Warning, which the branch you added in Step 6 prints. That is the payoff for
#: writing it: a threshold that seems to do nothing is usually a warning you can
#: now actually read.
#:
#: Also available: eager_eot_threshold (0.3-0.9, off by default, must be <=
#: EOT_THRESHOLD). It starts the LLM on a *probable* turn end and discards the
#: work if the user keeps talking -- lower latency, more LLM calls. Add it in the
#: provider below once the two constants make sense on their own.
#: --------------------------------------------------------------------------
EOT_THRESHOLD = 0.7  # Valid 0.5-0.9. Raise it to stop the agent cutting people off mid-thought, lower it for snappier replies at the cost of false turn ends.
EOT_TIMEOUT_MS = 5000  # Valid 500-60000. Hard ceiling: end the turn after this much silence, whatever the score says.


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
        listen=AgentV1SettingsAgentContextListen(
            provider=AgentV1SettingsAgentContextListenProvider_V2(
                type="deepgram",
                model="flux-general-en",  # Deepgram's general-purpose English voice agent model. Use flux-general-multi for auto-detection. See: https://developers.deepgram.com/docs/flux/language-prompting
                eot_threshold=EOT_THRESHOLD,  # Valid 0.5-0.9. Raise it to stop the agent cutting people off mid-thought, lower it for snappier replies at the cost of false turn ends.
                eot_timeout_ms=EOT_TIMEOUT_MS,  # Valid 500-60000. Hard ceiling: end the turn after this much silence no matter what the score says.
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


def handle_function_call(agent: AgentHandle, message: object) -> None:
    """Run every client-side function the agent asked for and return the results.

    The agent is mid-turn and blocked on these responses, so failures are
    reported back as the function's result rather than raised. A raised
    exception would escape into the SDK's receive loop, surface as
    EventType.ERROR, and drop the call.

    This runs on the SDK's receive loop thread, which is also the thread
    delivering audio. A slow function here stalls playback for everyone. Keep
    handlers fast, or hand the work to a thread and reply once it finishes.

    Args:
        agent: The connected agent, used to send each response.
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


def on_message(agent: AgentHandle, player: Player, message: object) -> None:
    """Handle one inbound frame from the agent.

    Unrecognized message types fall through to a plain print so that new server
    events stay visible rather than being silently dropped.

    Args:
        agent: The connected agent, used to reply to function calls.
        player: Where audio is played. send() queues a chunk, clear() throws
            away whatever is queued but not yet heard.
        message: Either raw bytes of Flux TTS audio, or a decoded model whose
            "type" attribute names the event.
    """
    if isinstance(message, bytes):
        player.send(message)
        return

    message_type = getattr(message, "type", "Unknown")

    if message_type == "SettingsApplied":
        print(">> Settings applied")
    elif message_type == "ConversationText":
        role = getattr(message, "role", "unknown")
        content = getattr(message, "content", "")
        print(f"[{role}] {content}")
    elif message_type == "UserStartedSpeaking":
        # Flux detected start-of-turn, so the agent has stopped sending audio --
        # but whatever it already sent is still queued, on this side of the
        # network and in the browser, and would keep talking over the user.
        # clear() throws both away. Nothing about that queue is worth keeping:
        # every byte in it was produced before the user opened their mouth.
        player.clear()
        print(">> User started speaking (barge-in: playback cleared)")
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
        #: ---- TODO (Step 8.1): Measure before you tune --------------------
        #: Uncomment the three lines below. total_latency is end-of-utterance to
        #: first audio byte -- the exact number the knobs in TODO 8.2 move, and
        #: the only honest way to tell whether a change helped. Everything else
        #: is impression.
        #:
        #: The report also carries ttt_token_latency, ttt_text_latency,
        #: ttt_tool_latency, ttt_thinking_latency, and tts_latency. Every field
        #: is optional -- absent, not zero, when it does not apply, which is why
        #: the None check below is not decoration.
        #:
        #: The browser has been showing this number all along, on the right of
        #: the activity line above the transcript. Watching it move while you
        #: talk is a faster feedback loop than reading the console; the print is
        #: what lets you keep a record across runs.
        #: ------------------------------------------------------------------
        # total = getattr(message, "total_latency", None)
        # if total is not None:
        #     print(f">> Latency: {total:.2f}s")
        pass
    elif message_type == "Error":
        code = getattr(message, "code", "unknown")
        description = getattr(message, "description", "unknown error")
        print(f">> Agent error: {code} - {description}")
    elif message_type == "Warning":
        # Non-fatal, and the place a rejected setting shows up -- a bad voice
        # name or a threshold outside its valid range warns here rather than
        # failing the handshake.
        code = getattr(message, "code", "unknown")
        description = getattr(message, "description", "unknown warning")
        print(f">> Agent warning: {code} - {description}")
    else:
        print(f">> {message_type}")


def on_media(agent: AgentHandle, audio: bytes) -> None:
    """Forward one captured chunk of microphone audio to the agent.

    Nothing here inspects the audio -- Flux decides where turns begin and end
    server-side, so there is no client-side voice activity detection to run.

    Args:
        agent: The connected agent.
        audio: One 80 ms chunk of linear16 PCM from the microphone.
    """
    agent.send_media(audio)


def main() -> None:
    """Serve the page and stream audio until interrupted.

    Everything about connection order lives in web/bridge.py: it waits for the
    browser's speaker before opening the Deepgram socket, and waits for the
    settings handshake before letting the microphone send anything. The agent
    discards media until that handshake completes, so the order matters.
    """
    bridge.run(settings=SETTINGS, on_message=on_message, on_media=on_media)


if __name__ == "__main__":
    main()
