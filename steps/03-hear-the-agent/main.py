"""Step 3 - Hear the agent.

Runs exactly as Step 2 left it: connects, applies settings, prints events.

The agent is already speaking. Run this file and watch the console -- after
">> Settings applied" you will see ">> AgentStartedSpeaking", and Flux TTS audio
is arriving on the socket right now. It is being thrown away, because nothing is
sending it anywhere.

This step gives it somewhere to go. By the end you will hear the greeting.

Where does it go? Into `player`, the second argument the bridge hands your
handler. In the browser that means: across the WebSocket, into a queue inside an
AudioWorklet, out the speaker. That queue is worth looking at --
web/static/worklets.js, class PlaybackProcessor -- because Step 5 is entirely
about throwing it away at the right moment.

Look for the "TODO (Step 3.x)" blocks below.

Run it with:  uv run steps/03-hear-the-agent/main.py
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

# Flux's turn detection knobs, at a balanced starting point. Step 8 moves them.
EOT_THRESHOLD = 0.7  # Valid 0.5-0.9. Raise it to stop the agent cutting people off mid-thought, lower it for snappier replies at the cost of false turn ends.
EOT_TIMEOUT_MS = 5000  # Valid 500-60000. Hard ceiling: end the turn after this much silence, whatever the score says.

SETTINGS = AgentV1Settings(
    audio=AgentV1SettingsAudio(
        input=AgentV1SettingsAudioInput(encoding="linear16", sample_rate=SAMPLE_RATE),
        output=AgentV1SettingsAudioOutput(encoding="linear16", sample_rate=SAMPLE_RATE),
    ),
    agent=AgentV1SettingsAgent(
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
            prompt="You are a helpful AI assistant. Keep your responses brief.",
        ),
        speak=SpeakSettingsV1(
            provider=SpeakSettingsV1Provider_Deepgram(
                type="deepgram",
                model="flux-alexis-en",
            ),
        ),
        greeting="Hello! I'm a Deepgram voice agent. What would you like to talk about?",
    ),
)


def on_message(agent: AgentHandle, player: Player, message: object) -> None:
    """Handle one inbound frame from the agent.

    Unrecognized message types fall through to a plain print so that new server
    events stay visible rather than being silently dropped.

    Args:
        agent: The connected agent. Unused until Step 7.
        player: Where audio is played. send() queues a chunk.
        message: Either raw bytes of Flux TTS audio, or a decoded model whose
            "type" attribute names the event.
    """
    if isinstance(message, bytes):
        # ---- TODO (Step 3.1): Play it -----------------------------------
        # This branch already catches every audio frame -- it just drops them.
        # Hand them to the player instead:
        #
        #   player.send(message)
        #
        # One line, and no error handling, which is the point of routing audio
        # through the bridge: a chunk that cannot be played is the bridge's
        # problem, not yours. Compare web/audio.py, where LocalPlayer.send
        # catches PortAudioError and drops the chunk rather than letting an
        # exception escape into the SDK's receive loop -- that loop wraps
        # itself in one try/except, so anything thrown here would be reported
        # as EventType.ERROR and would close the connection.
        #
        # Note there is no buffering to write. `player` queues, and the queue
        # drains at exactly the rate the speaker consumes it.
        # ------------------------------------------------------------------
        return

    message_type = getattr(message, "type", "Unknown")

    if message_type == "SettingsApplied":
        print(">> Settings applied")
    elif message_type == "ConversationText":
        role = getattr(message, "role", "unknown")
        content = getattr(message, "content", "")
        print(f"[{role}] {content}")
    # ---- TODO (Step 3.2): Narrate the turn --------------------------------
    # Right now every event you have not named prints as a bare
    # ">> SomeEventName" via the fallthrough at the bottom. Give the
    # interesting ones proper branches so the console reads like a transcript
    # of what the agent is doing:
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
    # LatencyReport gets an explicit `pass` rather than being left to the
    # fallthrough: it fires once per turn and would otherwise clutter the
    # transcript. Step 8 turns it into something useful.
    #
    # AgentAudioDone is worth a moment. It means the agent has finished
    # *sending* audio, not that you have finished hearing it -- there may be a
    # second of speech still queued in the browser. The two are different
    # events and Step 5 depends on the difference.
    # -----------------------------------------------------------------------
    elif message_type == "Error":
        code = getattr(message, "code", "unknown")
        description = getattr(message, "description", "unknown error")
        print(f">> Agent error: {code} - {description}")
    else:
        print(f">> {message_type}")


def main() -> None:
    """Serve the page and run the agent until interrupted.

    Still no on_media, so the microphone stays closed and the agent hangs up
    with CLIENT_MESSAGE_TIMEOUT after about fifteen seconds. Long enough to
    hear the greeting, which is all this step is for.
    """
    bridge.run(settings=SETTINGS, on_message=on_message)


if __name__ == "__main__":
    main()
