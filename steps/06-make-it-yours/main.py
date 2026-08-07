"""Step 7 - Make it yours.

Runs exactly as Step 6 left it: a tuned, interruptible voice agent.

Everything so far has been plumbing. This step is where the agent becomes
*yours* -- its job, its personality, its voice, its opening line. There is less
code here than in any other step and more to play with.

Look for the "TODO (Step 7.x)" blocks below.

Run it with:  uv run steps/07-make-it-yours/main.py
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

# Flux's turn detection knobs. Every turn gets an end-of-turn confidence score;
# these decide how much confidence is enough and how long silence may run.
EOT_THRESHOLD = 0.7  # Valid 0.5-0.9. Raise it to stop the agent cutting people off mid-thought, lower it for snappier replies at the cost of false turn ends.
EOT_TIMEOUT_MS = 5000  # Valid 500-60000. Hard ceiling: end the turn after this much silence, whatever the score says.
# Also available: eager_eot_threshold (0.3-0.9, off by default, must be <=
# EOT_THRESHOLD). It starts the LLM on a probable turn end and discards the work
# if the user keeps talking -- lower latency, more LLM calls.

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
            # ---- TODO (Step 7.3): Try a different brain -------------------
            # gpt-4o-mini is fast and cheap, which matters more than raw
            # capability when someone is waiting to hear a reply. Try
            # "gpt-4o" and listen for the extra latency before deciding it is
            # worth it -- the latency readout you turned on in Step 6 puts a
            # number on it. temperature controls variability: 0.0 for an agent
            # that must say the same thing every time, 1.0+ for a chatty one.
            #
            # Other providers are available here too (Anthropic, Google, Groq,
            # AWS Bedrock) via the matching ThinkSettingsV1Provider_* class.
            # ---------------------------------------------------------------
            provider=ThinkSettingsV1Provider_OpenAi(
                type="open_ai",
                model="gpt-4o-mini",
                temperature=0.7,
            ),
            # The prompt is prepended to every user turn before it reaches the
            # LLM. It is the agent's standing instructions -- personality, job,
            # and boundaries. Keep it short: every token here is re-sent on
            # every turn, and long prompts slow the first reply.
            # ---- TODO (Step 7.1): Give your agent a job -------------------
            # Replace the prompt below. Two rules that matter more than they
            # look:
            #
            #   1. Tell it that it is *speaking*. LLMs default to writing.
            #      Without this you get bullet points and asterisks read
            #      aloud, and it is jarring the first time you hear it:
            #        "You are speaking out loud, so never use markdown,
            #         bullet points, or emoji."
            #
            #   2. Tell it to be brief. Text-chat length answers feel
            #      interminable in a conversation.
            #
            # Then give it an actual job -- a barista taking an order, a
            # support agent for a product you know, a dungeon master. Specific
            # beats generic.
            prompt="You are a helpful AI assistant. Keep your responses brief.",
            # ---------------------------------------------------------------
        ),
        # Flux TTS is Deepgram's streaming, turn-based voice engine built for
        # voice agents. The "flux-" model prefix routes the agent to the v2
        # Speak backend (wss://api.deepgram.com/v2/speak) automatically.
        speak=SpeakSettingsV1(
            provider=SpeakSettingsV1Provider_Deepgram(
                type="deepgram",
                # ---- TODO (Step 7.2): Pick a voice ------------------------
                # Swap flux-alexis-en for another Flux voice. The full list is
                # at https://developers.deepgram.com/docs/tts-models
                #
                # Deliberately misspell one first and run it. You will get a
                # ">> Agent warning" once you finish TODO 7.4 -- a rejected
                # voice is non-fatal, and the agent falls back rather than
                # failing the handshake. Knowing that saves you an hour some
                # day when an agent sounds wrong and nothing has errored.
                # -----------------------------------------------------------
                model="flux-alexis-en",
            ),
        ),
        # The agent's first utterance, spoken as soon as settings are applied.
        # It is added to the conversation history, so the LLM knows it already
        # said this and will not repeat itself on the first real turn.
        # ---- TODO (Step 7.2b): Write a new opening line -------------------
        # Make it match the job you gave it above. This is the only line the
        # agent says before it knows anything about the user, so it is doing
        # all the work of setting expectations.
        greeting="Hello! I'm a Deepgram voice agent. What would you like to talk about?",
        # -------------------------------------------------------------------
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
        # total_latency is end-of-utterance to first audio byte -- the number
        # the turn-detection knobs above move. Also carries ttt_token_latency,
        # ttt_text_latency, ttt_tool_latency, ttt_thinking_latency, and
        # tts_latency. Every field is optional -- absent, not zero, when it
        # doesn't apply.
        total = getattr(message, "total_latency", None)
        if total is not None:
            print(f">> Latency: {total:.2f}s")
    elif message_type == "Error":
        code = getattr(message, "code", "unknown")
        description = getattr(message, "description", "unknown error")
        print(f">> Agent error: {code} - {description}")
    # ---- TODO (Step 7.4): Surface warnings --------------------------------
    # Add a branch for "Warning", printing .code and .description the same way
    # the Error branch above does:
    #
    #   elif message_type == "Warning":
    #       code = getattr(message, "code", "unknown")
    #       description = getattr(message, "description", "unknown warning")
    #       print(f">> Agent warning: {code} - {description}")
    #
    # Warnings are where rejected settings show up. A misspelled voice or a
    # threshold outside its valid range arrives here rather than failing the
    # handshake -- so without this branch, a bad setting is silently ignored
    # and you are left wondering why nothing changed.
    #
    # The browser shows warnings whether or not you write this branch, in the
    # box above the transcript. That is the bridge mirroring events to the
    # page, not this file -- and it is exactly the sort of thing you would not
    # get for free in your own agent, which is why the branch is still worth
    # writing.
    # -----------------------------------------------------------------------
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
