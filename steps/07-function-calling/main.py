"""Step 7 - Function calling.

Runs exactly as Step 6 left it: a voice agent with your persona and voice.

Your job in this step is to let the agent run Python. You will advertise a
function in the agent's settings, handle the FunctionCallRequest the agent
sends when the LLM decides to use it, and send the result back.

Look for the "TODO (Step 7.x)" blocks below and work through them in order.

Run it with:  uv run steps/07-function-calling/main.py
"""

# ---- TODO (Step 7.1): Imports ---------------------------------------------
# You need five more imports for this step. Add them to the groups below,
# keeping each group alphabetical:
#
#   standard library:
#     import json                                 (parse the LLM's arguments)
#     from datetime import datetime               (the function's actual work)
#     from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
#
#   third party:
#     AgentV1SendFunctionCallResponse   -> into the deepgram.agent.v1.types
#                                          block, first alphabetically
#     from deepgram.types.think_settings_v1functions_item import (
#         ThinkSettingsV1FunctionsItem,
#     )
# ---------------------------------------------------------------------------

from deepgram.agent.v1.types import (
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
from deepgram.types.think_settings_v1provider import ThinkSettingsV1Provider_OpenAi
from dotenv import load_dotenv

from web import AgentHandle, Player, bridge

load_dotenv()

SAMPLE_RATE = 24000  # Deepgram's recommended sample rate for voice agents. For telephony, 8000 is recommended.
# The browser captures in 80 ms chunks -- the size Flux's turn detection is
# tuned for. That interacts with everything below: no threshold setting can
# detect a turn end sooner than the chunk carrying it arrives.

# Flux's turn detection knobs, at a balanced starting point. Every turn gets an
# end-of-turn confidence score; these decide how much confidence is enough and
# how long silence may run. Step 8 is where you move them.
EOT_THRESHOLD = 0.7  # Valid 0.5-0.9. Raise it to stop the agent cutting people off mid-thought, lower it for snappier replies at the cost of false turn ends.
EOT_TIMEOUT_MS = 5000  # Valid 500-60000. Hard ceiling: end the turn after this much silence, whatever the score says.

# ---- TODO (Step 7.2): Write the function ----------------------------------
# Write the Python the agent will call. Signature:
#
#   def get_current_time(timezone: str = "UTC") -> str:
#
# It should build a ZoneInfo from `timezone`, falling back to UTC inside a
# try/except (ZoneInfoNotFoundError, ValueError) -- the LLM invents
# plausible-but-wrong timezone names often enough that raising would end
# otherwise fine conversations.
#
# Return a *sentence*, not a data structure. Whatever you return is fed back to
# the LLM and read aloud, so "It is 2:15 PM on Tuesday, August 05 in
# America/New_York." works far better than {"hour": 14, "minute": 15}.
#
# Note: strftime's %-I (hour with no leading zero) is a glibc/BSD extension and
# fails on Windows. Use "%I:%M %p" and .lstrip("0") instead.
#
# Then map the advertised name to the callable:
#
#   FUNCTION_HANDLERS = {"get_current_time": get_current_time}
#
# Docstrings are required here -- ruff is configured with pydocstyle (google).
# ---------------------------------------------------------------------------

# ---- TODO (Step 7.3): Advertise the function ------------------------------
# Build the list the agent is told about. This is advertising only: the LLM
# decides *whether* to call, your code decides *what happens* when it does.
#
#   FUNCTIONS = [
#       ThinkSettingsV1FunctionsItem(
#           name="get_current_time",
#           description=(
#               "Get the current date and time in a given IANA timezone. Use "
#               "this whenever the user asks what time it is or what today's "
#               "date is."
#           ),
#           parameters={  # plain JSON Schema, as the LLM's tool API expects
#               "type": "object",
#               "properties": {
#                   "timezone": {
#                       "type": "string",
#                       "description": "IANA timezone name, e.g. Europe/London.",
#                   },
#               },
#               "required": ["timezone"],
#           },
#       ),
#   ]
#
# The description is the prompt. It is the only thing the LLM reads when
# deciding to call, so spell out *when* to use it, not just what it does.
#
# Leaving "endpoint" unset is what marks this function client-side -- that is
# why Deepgram sends the call down the socket to you instead of calling an HTTP
# endpoint itself.
# ---------------------------------------------------------------------------

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
            # ---- TODO (Step 7.4): Attach the functions --------------------
            # Add:  functions=FUNCTIONS,
            # ---------------------------------------------------------------
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

# ---- TODO (Step 7.5): Handle the call -------------------------------------
# Write a module-level function:
#
#   def handle_function_call(agent: AgentHandle, message: object) -> None:
#
# A FunctionCallRequest carries a "functions" list. Loop over it; each entry has
# .id, .name, and .arguments (a JSON *string*, not a dict). For each one:
#
#   1. Look the name up in FUNCTION_HANDLERS.
#   2. Call it with  handler(**json.loads(arguments))
#   3. Send the result back:
#
#        agent.send_function_call_response(
#            AgentV1SendFunctionCallResponse(id=call.id, name=name, content=content),
#        )
#
# Two things that will bite you:
#
#   * Catch exceptions and return the error text as `content`. The agent is
#     mid-turn and blocked waiting on you. A raised exception escapes into the
#     SDK's receive loop, surfaces as EventType.ERROR, and drops the call.
#
#   * This runs on the SDK's receive loop -- the same thread delivering audio.
#     A slow function stalls playback. Keep handlers fast, or hand the work to
#     a thread and reply when it finishes. Routing audio through the browser
#     does not change this: the bytes still pass through this thread on their
#     way out.
#
# Print the call and the result. You want to see what the LLM actually passed.
# ---------------------------------------------------------------------------


def on_message(agent: AgentHandle, player: Player, message: object) -> None:
    """Handle one inbound frame from the agent.

    Unrecognized message types fall through to a plain print so that new server
    events stay visible rather than being silently dropped.

    Args:
        agent: The connected agent, used to reply to function calls.
        player: Where audio is played. send() queues a chunk; clear() throws
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
        player.clear()
        print(">> User started speaking (barge-in: playback cleared)")
    elif message_type == "AgentThinking":
        print(">> Agent thinking...")
    elif message_type == "AgentStartedSpeaking":
        print(">> Agent started speaking")
    elif message_type == "AgentAudioDone":
        print(">> Agent finished speaking")
    # ---- TODO (Step 7.6): Dispatch the request ----------------------------
    # Add a branch, above the LatencyReport one:
    #
    #   elif message_type == "FunctionCallRequest":
    #       handle_function_call(agent, message)
    #
    # Without it, the fallthrough at the bottom prints ">> FunctionCallRequest"
    # and the agent waits forever for a reply that never comes -- a useful
    # thing to see once on purpose.
    # -----------------------------------------------------------------------
    elif message_type == "LatencyReport":
        # One report per turn, arriving right after the reply starts. Printed,
        # it buries the conversation -- Step 8 turns it on deliberately, once
        # there is a reason to read it. The browser shows the number either
        # way, on the right of the activity line above the transcript.
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
    """Serve the page and run the agent until interrupted."""
    bridge.run(settings=SETTINGS, on_message=on_message, on_media=on_media)


if __name__ == "__main__":
    main()
