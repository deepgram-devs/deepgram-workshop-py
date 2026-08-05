"""Step 2 - Connect to the Voice Agent.

This is where the agent program begins. Step 1 only proved your machine and
your API key work; nothing from it carries forward.

Run this file as-is and you will see ">> Connection opened" and then, five
seconds later, ">> Connection closed". A socket is open to Deepgram and nothing
is being said over it.

Your job is the handshake: describe the agent you want, send it, and wait for
the server to confirm. No audio yet -- Step 3 handles that.

Look for the "TODO (Step 2.x)" blocks below.
"""

import os
import threading
import time

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

# Reads .env from the repository root. python-dotenv walks up from this file's
# directory, so it finds the same .env no matter which step you run or which
# directory you run it from.
load_dotenv()

# Everything the agent sends is either a decoded event model or raw TTS audio.
AgentMessage = str | bytes

# The audio format, agreed with the server in SETTINGS below and used by the
# sound device streams from Step 3 onward. Both ends must match exactly.
SAMPLE_RATE = 24000 # Deepgram's recommended sample rate for voice agents. For telephony, 8000 is recommended.
CHANNELS = 1 # Deepgram's recommended channel count for voice agents. Mono is the most widely supported format across platforms and languages.
DTYPE = "int16" # Deepgram's recommended PCM format for voice agents. Raw 16-bit signed integer PCM is the most widely supported format across platforms and languages.
BLOCK_SIZE = SAMPLE_RATE * 80 // 1000 # 80 ms of audio per block, the chunk size Flux is tuned for. Smaller blocks add websocket overhead; larger ones delay turn detection.

# One object describes the entire agent: how it hears, how it thinks, how it
# speaks. Read it top to bottom -- it is the most important thing in this file,
# and every later step is either adding to it or reacting to what it produces.
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
    """Open the agent connection, apply SETTINGS, and print what comes back.

    Raises:
        TimeoutError: If the agent does not acknowledge SETTINGS within ten
            seconds.
    """
    # No key means api_key=None, and the failure surfaces later as a confusing
    # connection error. Step 1 checked this properly -- worth remembering when
    # something inexplicable happens here.
    client = DeepgramClient(api_key=os.getenv("DEEPGRAM_API_KEY"))

    with client.agent.v1.connect() as agent:
        # ---- TODO (Step 2.1): Handle inbound messages ---------------------
        # First, a way to find out when the handshake has completed. The
        # messages arrive on a background thread, so the main thread needs
        # something to block on:
        #
        #   settings_applied = threading.Event()
        #
        # Then write the handler. Everything the agent sends arrives here:
        #
        #   def on_message(message: AgentMessage) -> None:
        #       """Handle one inbound frame from the agent."""
        #       if isinstance(message, bytes):
        #           # Flux TTS audio. It is already arriving -- there is just
        #           # nowhere to play it yet. Step 3 fixes that.
        #           return
        #
        #       message_type = getattr(message, "type", "Unknown")
        #
        #       if message_type == "SettingsApplied":
        #           print(">> Settings applied")
        #           settings_applied.set()
        #       elif message_type == "ConversationText":
        #           role = getattr(message, "role", "unknown")
        #           content = getattr(message, "content", "")
        #           print(f"[{role}] {content}")
        #       elif message_type == "Error":
        #           code = getattr(message, "code", "unknown")
        #           description = getattr(message, "description", "unknown error")
        #           print(f">> Agent error: {code} - {description}")
        #       else:
        #           print(f">> {message_type}")
        #
        # Two deliberate choices worth copying into your own agents:
        #
        #   * The bytes check comes first. Audio is not a JSON event and has no
        #     .type -- reaching for one would give you "Unknown" thousands of
        #     times a minute.
        #
        #   * The else branch prints instead of ignoring. Deepgram adds server
        #     events over time; the fallthrough means new ones show up in your
        #     console rather than vanishing. You will use it in Step 5.
        #
        # Note the getattr(..., default) calls everywhere. These models come off
        # the wire with optional fields -- absent, not empty -- so direct
        # attribute access is a crash waiting for an unusual turn.
        # -------------------------------------------------------------------

        agent.on(EventType.OPEN, lambda _: print(">> Connection opened"))
        # ---- TODO (Step 2.2): Register the handler ------------------------
        # Add:  agent.on(EventType.MESSAGE, on_message)
        #
        # Put it with the others below. Registration has to happen before
        # start_listening(), or the first events are delivered to nobody.
        # -------------------------------------------------------------------
        agent.on(EventType.CLOSE, lambda _: print(">> Connection closed"))
        agent.on(EventType.ERROR, lambda error: print(f">> Error: {error}"))

        # The receive loop is blocking, so it gets its own thread. daemon=True
        # means it will not keep the process alive once main() returns.
        listener = threading.Thread(target=agent.start_listening, daemon=True)
        listener.start()

        # ---- TODO (Step 2.3): Send the settings and wait ------------------
        # Replace the sleep below with:
        #
        #   print("Sending agent settings...")
        #   agent.send_settings(SETTINGS)
        #
        #   if not settings_applied.wait(10):
        #       raise TimeoutError("Timed out waiting for agent settings to apply.")
        #
        #   print("\nAgent is live. (Step 3 adds the speaker.)\n")
        #   time.sleep(10)
        #
        # That sleep is ten seconds for a reason: the agent expects a
        # *continuous* media stream, and hangs up with a CLIENT_MESSAGE_TIMEOUT
        # error after about fifteen seconds of receiving none. Nothing is
        # sending audio until Step 4, so this exits before that fires. Raise it
        # to 20 once, on purpose, to see the error -- recognising it later is
        # worth the ten seconds.
        #
        # Do not skip the wait. The agent throws away any media it receives
        # before the handshake completes, so every later step opens the
        # microphone *after* this line. Blocking here is what makes that
        # ordering guaranteed rather than a race you win most of the time.
        #
        # Ten seconds is generous. If it ever fires, the cause is almost always
        # a rejected setting or a bad API key rather than a slow network.
        # -------------------------------------------------------------------
        print("\nConnected. Nothing has been sent yet.\n")
        time.sleep(5)


if __name__ == "__main__":
    main()
