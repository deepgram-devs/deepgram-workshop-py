"""Step 6 - Tune turn detection.

Runs exactly as Step 5 left it: a working, interruptible voice agent using
Flux's default turn-detection settings.

This step is mostly dials rather than code. You will expose Flux's end-of-turn
knobs, turn on the per-turn latency report, and then actually listen to what
moving them does. Turn detection is the single biggest lever on whether an
agent feels natural or infuriating, and the only way to calibrate it is by ear.

Look for the "TODO (Step 6.x)" blocks below.

Run it with:  uv run steps/06-tune-turns/main.py
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

from web import AgentHandle, Player, bridge

load_dotenv()

SAMPLE_RATE = 24000  # Deepgram's recommended sample rate for voice agents. For telephony, 8000 is recommended.
# The browser captures in 80 ms chunks -- the size Flux's turn detection is
# tuned for. That interacts with everything below: no threshold setting can
# detect a turn end sooner than the chunk carrying it arrives.

# ---- TODO (Step 6.1): Expose the turn-detection knobs ---------------------
# Flux scores every turn for end-of-turn confidence. Two settings decide how
# much confidence is enough, and how long silence may run before the turn ends
# regardless. Both are optional -- omitting them, as this file does now, uses
# the server defaults, which is why Step 5 already worked.
#
# Add two constants here:
#
#   EOT_THRESHOLD = 0.7    # valid 0.5 - 0.9
#   EOT_TIMEOUT_MS = 5000  # valid 500 - 60000
#
# EOT_THRESHOLD is the confidence Flux needs before it calls the turn over.
# Raise it and the agent stops cutting you off mid-thought; lower it and
# replies come faster, at the cost of the agent jumping in when you pause.
#
# EOT_TIMEOUT_MS is the hard ceiling: end the turn after this much silence no
# matter what the score says.
#
# Also available: eager_eot_threshold (0.3-0.9, off by default, must be <=
# EOT_THRESHOLD). It starts the LLM on a probable turn end and discards the
# work if the user keeps talking -- lower latency, more LLM calls.
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
                # ---- TODO (Step 6.2): Wire the knobs up -------------------
                # Pass the two constants from TODO 6.1:
                #
                #   eot_threshold=EOT_THRESHOLD,
                #   eot_timeout_ms=EOT_TIMEOUT_MS,
                #
                # Values outside the valid ranges do not fail the handshake --
                # they come back as a Warning message, which nothing handles
                # yet. Step 7 adds that branch. For now, if a value seems to do
                # nothing, that is probably why.
                # -----------------------------------------------------------
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


def on_message(agent: AgentHandle, player: Player, message: object) -> None:
    """Handle one inbound frame from the agent.

    Unrecognized message types fall through to a plain print so that new server
    events stay visible rather than being silently dropped.

    Args:
        agent: The connected agent. Unused until Step 8.
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
    elif message_type == "LatencyReport":
        # One report per turn, arriving right after the reply starts.
        # ---- TODO (Step 6.3): Measure what you changed --------------------
        # Uncomment the three lines below. total_latency is end-of-utterance
        # to first audio byte -- the exact number the knobs in TODO 6.1 move,
        # and the only honest way to tell whether a change helped.
        #
        # The report also carries ttt_token_latency, ttt_text_latency,
        # ttt_tool_latency, ttt_thinking_latency, and tts_latency. Every field
        # is optional -- absent, not zero, when it does not apply, which is why
        # the None check below is not decoration.
        #
        # The browser already shows this number, on the right of the activity
        # line above the transcript. Watching it move while you talk is a
        # faster feedback loop than reading the console.
        # -------------------------------------------------------------------
        # total = getattr(message, "total_latency", None)
        # if total is not None:
        #     print(f">> Latency: {total:.2f}s")
        pass
    elif message_type == "Error":
        code = getattr(message, "code", "unknown")
        description = getattr(message, "description", "unknown error")
        print(f">> Agent error: {code} - {description}")
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
