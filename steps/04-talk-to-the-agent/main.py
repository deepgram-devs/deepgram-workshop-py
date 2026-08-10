"""Step 4 - Talk to the agent.

You can hear it. It cannot hear you. This step closes the loop, and at the end
of it you have a working voice agent.

So far the agent has hung up on you every time, because it expects a continuous
media stream and has been receiving none. Send it audio and that stops
happening.

The microphone itself lives in the browser, and it has been open since you
pressed Connect -- that is what the level meter on the page has been showing.
What is missing is the instruction to do anything with it.

Look for the "TODO (Step 4.x)" blocks below. Inside them, "#:" marks the
instructions and everything else is code, commented out at the indentation it
belongs at: select those lines and press Cmd+/ (Ctrl+/ on Windows and Linux) to
uncomment them where they sit.

Run it with:  uv run steps/04-talk-to-the-agent/main.py
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
# tuned for. Smaller chunks pay websocket overhead per chunk; larger ones delay
# turn detection, because Flux cannot score an end-of-turn until the chunk
# containing it arrives. web/session.py derives that size from SAMPLE_RATE and
# sends it to the page, so this constant is the only place it is written down.

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
        player.send(message)
        return

    message_type = getattr(message, "type", "Unknown")

    if message_type == "SettingsApplied":
        print(">> Settings applied")
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
        pass
    elif message_type == "Error":
        code = getattr(message, "code", "unknown")
        description = getattr(message, "description", "unknown error")
        print(f">> Agent error: {code} - {description}")
    else:
        print(f">> {message_type}")


#: ---- TODO (Step 4.1): Send the microphone up -----------------------------
#: Write the other half of the conversation. Every 80 ms the browser's capture
#: worklet hands the bridge a chunk of PCM, and the bridge calls this with it:
#:
# def on_media(agent: AgentHandle, audio: bytes) -> None:
#     """Forward one captured chunk of microphone audio to the agent.
#
#     Args:
#         agent: The connected agent.
#         audio: One 80 ms chunk of linear16 PCM from the microphone.
#     """
#     agent.send_media(audio)
#:
#: That is the whole thing, and the shortness is the lesson. Nothing here
#: inspects the audio, measures its volume, trims silence, or decides whether
#: the user is talking. Flux does turn detection inside the model, server-side,
#: so there is no voice activity detection to write -- which is most of what
#: makes a voice agent client hard in the general case. Your job is to keep the
#: pipe full.
#:
#: Nor does anything here block. agent.send_media() hands the chunk to a
#: dedicated sender thread and returns immediately; see AgentHandle in
#: web/session.py for why a blocking send would be a serious problem.
#:
#: Two things the browser is doing for you, which you would otherwise be
#: writing yourself -- see web/static/worklets.js:
#:
#:   * Chunking. The audio hardware delivers 128 frames at a time. The capture
#:     worklet accumulates those into the 1920-frame chunks Flux wants.
#:
#:   * Resampling. Most microphones run at 48 kHz. The browser hands you 24 kHz
#:     because that is what SETTINGS asked for.
#: --------------------------------------------------------------------------


def main() -> None:
    """Serve the page and run the agent until interrupted."""
    #: ---- TODO (Step 4.2): Open the microphone ----------------------------
    #: Add on_media to the call below:
    #:
    # bridge.run(settings=SETTINGS, on_message=on_message, on_media=on_media)
    #:
    #: Passing it is what tells the browser to start capturing. Until now the
    #: bridge has been sending the page a "do not capture" flag along with the
    #: settings handshake -- see _mirror() in web/session.py.
    #:
    #: Note *when* capture starts: only after SettingsApplied arrives. The agent
    #: discards media until the handshake completes, so starting any earlier
    #: throws away your first words. The bridge enforces that ordering; it is
    #: the reason the page waits for a "ready" message rather than sending audio
    #: the moment the socket opens.
    #:
    #: Then talk to it. The agent stops hanging up, because it is finally
    #: receiving the continuous media stream it has been waiting for.
    #: ----------------------------------------------------------------------
    bridge.run(settings=SETTINGS, on_message=on_message)


if __name__ == "__main__":
    main()
