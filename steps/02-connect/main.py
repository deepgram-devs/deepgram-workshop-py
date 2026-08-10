"""Step 2 - Connect to the Voice Agent.

This is where the agent program begins. Step 1 only proved your machine and
your API key work; nothing from it carries forward.

Run this file as-is and it opens a page in your browser with a Connect button
that does nothing useful yet. Your job is the handshake: describe the agent you
want, hand it to the bridge, and watch the server confirm it.

No audio yet -- Step 3 handles that. The agent expects a continuous media
stream and hangs up with CLIENT_MESSAGE_TIMEOUT after about fifteen seconds of
receiving none, so this step ends by itself. That is the correct ending.

Look for the "TODO (Step 2.x)" blocks below. Inside them, "#:" marks the
instructions and everything else is code, commented out at the indentation it
belongs at: select those lines and press Cmd+/ (Ctrl+/ on Windows and Linux) to
uncomment them where they sit.

Run it with:  uv run steps/02-connect/main.py
"""

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

# The browser bridge. It owns the web server, the WebSocket to the page, and
# the threads around Deepgram's blocking socket -- everything that is the same
# in every step. You never edit it, but it is worth reading: web/session.py is
# where the connection ordering this step depends on actually lives.
#
# AgentHandle and Player are unused until you write on_message below, which is
# why they are imported for you: the types your editor completes against should
# already be here when you start typing, not something you have to notice.
from web import AgentHandle, Player, bridge  # noqa: F401 -- used by the on_message you are about to write

# Reads .env from the repository root. python-dotenv walks up from this file's
# directory, so it finds the same .env no matter which step you run or which
# directory you run it from.
load_dotenv()

# The audio format, agreed with the server in SETTINGS below. The browser reads
# it back from the bridge and configures its microphone and speaker to match,
# so this constant is the only place it is written down.
SAMPLE_RATE = 24000  # Deepgram's recommended sample rate for voice agents. For telephony, 8000 is recommended.

# Flux's turn detection knobs. Every turn gets an end-of-turn confidence score;
# these decide how much confidence is enough and how long silence may run. The
# values below are a balanced starting point -- Step 8 is where you move them
# and hear what each one costs.
EOT_THRESHOLD = 0.7  # Valid 0.5-0.9. Raise it to stop the agent cutting people off mid-thought, lower it for snappier replies at the cost of false turn ends.
EOT_TIMEOUT_MS = 5000  # Valid 500-60000. Hard ceiling: end the turn after this much silence, whatever the score says.

# One object describes the entire agent: how it hears, how it thinks, how it
# speaks. Read it top to bottom -- it is the most important thing in this file,
# and every later step is either adding to it or reacting to what it produces.
SETTINGS = AgentV1Settings(
    audio=AgentV1SettingsAudio(
        # linear16 is raw 16-bit signed PCM, mono. The most widely supported
        # format across platforms and languages, and what the browser's audio
        # worklets produce and consume.
        input=AgentV1SettingsAudioInput(encoding="linear16", sample_rate=SAMPLE_RATE),
        output=AgentV1SettingsAudioOutput(encoding="linear16", sample_rate=SAMPLE_RATE),
    ),
    agent=AgentV1SettingsAgent(
        # Flux is Deepgram's conversational speech-to-text model, built for
        # voice agents. The "v2" provider version routes the agent to the v2
        # Listen backend (wss://api.deepgram.com/v2/listen), where the flux
        # models live. Turn detection is part of the model, so its thresholds
        # are configured here -- Step 8 turns those knobs.
        listen=AgentV1SettingsAgentContextListen(
            provider=AgentV1SettingsAgentContextListenProvider_V2(
                type="deepgram",
                model="flux-general-en",  # Deepgram's general-purpose English voice agent model. Use flux-general-multi for auto-detection. See: https://developers.deepgram.com/docs/flux/language-prompting
                eot_threshold=EOT_THRESHOLD,
                eot_timeout_ms=EOT_TIMEOUT_MS,
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


#: ---- TODO (Step 2.1): Handle inbound messages ----------------------------
#: Everything the agent sends arrives in one function. Uncomment it here:
#:
# def on_message(agent: AgentHandle, player: Player, message: object) -> None:
#     """Handle one inbound frame from the agent.
#
#     Args:
#         agent: The connected agent. Unused until Step 7.
#         player: Where audio is played. Unused until Step 3.
#         message: Either raw bytes of Flux TTS audio, or a decoded model
#             whose "type" attribute names the event.
#     """
#     if isinstance(message, bytes):
#         # Flux TTS audio. It is already arriving -- there is just nowhere
#         # to play it yet. Step 3 fixes that.
#         return
#
#     message_type = getattr(message, "type", "Unknown")
#
#     if message_type == "SettingsApplied":
#         print(">> Settings applied")
#     elif message_type == "ConversationText":
#         role = getattr(message, "role", "unknown")
#         content = getattr(message, "content", "")
#         print(f"[{role}] {content}")
#     elif message_type == "Error":
#         code = getattr(message, "code", "unknown")
#         description = getattr(message, "description", "unknown error")
#         print(f">> Agent error: {code} - {description}")
#     else:
#         print(f">> {message_type}")
#:
#: Three deliberate choices worth copying into your own agents:
#:
#:   * The bytes check comes first. Audio is not a JSON event and has no
#:     .type -- reaching for one would give you "Unknown" thousands of times
#:     a minute.
#:
#:   * The else branch prints instead of ignoring. Deepgram adds server events
#:     over time; the fallthrough means new ones show up in your console rather
#:     than vanishing. You will use it in Step 5.
#:
#:   * getattr(..., default) everywhere. These models come off the wire with
#:     optional fields -- absent, not empty -- so direct attribute access is a
#:     crash waiting for an unusual turn.
#:
#: The signature is fixed: the bridge calls this with three arguments whether
#: you use them or not. `player` starts earning its place in Step 3.
#: --------------------------------------------------------------------------


def main() -> None:
    """Serve the page and run the agent until interrupted.

    The bridge does the parts that are identical in every step: it starts a web
    server, waits for the browser's speaker to be ready before opening the
    Deepgram socket, applies SETTINGS, and waits for the agent to acknowledge
    them. The agent discards media until that handshake completes, so the order
    matters -- see _run() in web/session.py for exactly how it is enforced.
    """
    #: ---- TODO (Step 2.2): Hand your agent to the bridge ------------------
    #: Uncomment this, then delete the placeholder call below it:
    #:
    # bridge.run(settings=SETTINGS, on_message=on_message)
    #:
    #: Note what is *not* passed: on_media. Without it the bridge never opens
    #: the microphone at all, which is why this step sends no audio and gets
    #: hung up on. Step 4 adds it.
    #: ----------------------------------------------------------------------
    bridge.run(settings=SETTINGS, on_message=lambda agent, player, message: None)


if __name__ == "__main__":
    main()
