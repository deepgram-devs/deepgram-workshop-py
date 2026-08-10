"""Step 5 - Barge-in.

Runs exactly as Step 4 left it: a full two-way conversation.

BEFORE YOU WRITE ANY CODE, run this file and interrupt the agent mid-sentence.
Talk over it. It keeps going, cheerfully talking across you, while the console
prints ">> UserStartedSpeaking". That gap between what the server knows and what
your speaker is doing is the bug you are about to fix, and it is the difference
between a demo and something a person would willingly use.

Look for the "TODO (Step 5.1)" block below. Inside them, "#:" marks the
instructions and everything else is code, commented out at the indentation it
belongs at: select those lines and press Cmd+/ (Ctrl+/ on Windows and Linux) to
uncomment them where they sit.

Run it with:  uv run steps/05-barge-in/main.py
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
    #: ---- TODO (Step 5.1): Stop talking when the user starts --------------
    #: Add a branch here for "UserStartedSpeaking":
    #:
    # elif message_type == "UserStartedSpeaking":
    #     player.clear()
    #     print(">> User started speaking (barge-in: playback cleared)")
    #:
    #: What has already happened by the time this arrives: Flux detected
    #: start-of-turn server-side and the agent stopped sending audio. The
    #: problem is everything it *already* sent, which is queued and will keep
    #: playing over the user for as long as it takes to drain -- easily a second
    #: or two. Every byte of it was produced before the user opened their mouth,
    #: so none of it is worth keeping.
    #:
    #: One call, and it is worth knowing what it has to do, because you will
    #: write this yourself the next time you build one of these. There are two
    #: queues, and clearing only one leaves the bug in place:
    #:
    #:   * The browser's playback queue, inside an AudioWorklet. See
    #:     PlaybackProcessor in web/static/worklets.js -- the "clear" message
    #:     empties it.
    #:
    #:   * The queue on *this* side, holding audio that arrived from Deepgram
    #:     but has not yet been sent to the browser. Telling the page to flush
    #:     while seconds of TTS still sit here just means it plays a moment
    #:     later. See Outbox.drop_audio in web/audio.py, and note the ordering:
    #:     drop first, *then* send the clear.
    #:
    #: The equivalent trap in the PortAudio version is stop() versus abort() --
    #: stop() drains the buffer, playing everything already queued before it
    #: stops, which is precisely the behaviour you are trying to eliminate.
    #: LocalPlayer.clear in web/audio.py uses abort() for that reason.
    #:
    #: Note there is no client-side voice activity detection anywhere in this
    #: file. Flux does turn detection inside the model; the client's entire
    #: obligation is reacting to this one message promptly.
    #: ----------------------------------------------------------------------
    elif message_type == "AgentThinking":
        print(">> Agent thinking...")
    elif message_type == "AgentStartedSpeaking":
        print(">> Agent started speaking")
    elif message_type == "AgentAudioDone":
        print(">> Agent finished speaking")
    elif message_type == "LatencyReport":
        # One report per turn, arriving right after the reply starts. Printed,
        # it buries the conversation -- Step 8 turns it on deliberately.
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
