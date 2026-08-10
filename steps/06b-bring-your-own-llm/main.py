"""Step 6b - Bring your own LLM (optional).

Runs exactly as Step 6 left it, with the prompt and voice reset to neutral.

Optional. Every provider so far has been one Deepgram brokered for you -- your
Deepgram key paid for the LLM call and no second account was involved. This step
is what happens when the brain has to be *yours*: your AWS account, your model
access, your bill. It needs AWS credentials with Bedrock access, and Bedrock
model access is granted per model and per region, so it is not something you can
usually sort out in the five minutes this step takes.

Skipping it costs you nothing. Step 7 continues from Step 6 either way, and this
file falls back to OpenAI when no AWS credentials are present -- so it runs
whether or not you finish it.

Look for the "TODO (Step 6b.x)" blocks below.

Run it with:  uv run steps/06b-bring-your-own-llm/main.py
"""

# ---- TODO (Step 6b.1): Imports --------------------------------------------
# You need three more imports for this step. Add them to the third-party block
# below, keeping it alphabetical:
#
#   from deepgram.types.aws_bedrock_think_provider_credentials import (
#       AwsBedrockThinkProviderCredentials,
#   )
#   from deepgram.types.think_settings_v1endpoint import ThinkSettingsV1Endpoint
#   ThinkSettingsV1Provider_AwsBedrock  -> alongside ThinkSettingsV1Provider_OpenAi
#                                          on the think_settings_v1provider line
# ---------------------------------------------------------------------------

import os

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

# Everything Bedrock needs comes from .env, because none of it belongs in a file
# you might commit. See .env.example -- the whole block is optional and only
# this step reads it.
AWS_REGION = os.getenv("AWS_REGION", "us-east-2")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_SESSION_TOKEN = os.getenv("AWS_SESSION_TOKEN", "")  # STS only. Leave it unset for long-lived IAM keys.

# Bedrock model IDs are passed through to Bedrock untouched, so this is a plain
# string with no validation behind it -- a typo comes back from AWS, not from
# the SDK. The "us." prefix is a cross-region inference profile and has to match
# the region below.
BEDROCK_MODEL = os.getenv("AWS_BEDROCK_MODEL") or "us.anthropic.claude-3-5-haiku-20241022-v1:0"

# One prompt, used whichever provider ends up answering. Keeping it out of the
# branches below is the only reason they stay readable.
PROMPT = (
    "You are a helpful AI assistant. Keep your responses brief. "
    "You are speaking out loud, so never use markdown, bullet points, or emoji."
)


def think_settings() -> ThinkSettingsV1:
    """Build the think settings, on Bedrock when AWS credentials are present.

    Falling back to OpenAI rather than failing is deliberate. This step is
    optional, and the file has to keep running for someone who never got Bedrock
    access -- including someone who is halfway through the TODO below.

    Returns:
        The think settings the agent is configured with.
    """
    # ---- TODO (Step 6b.2): Think on Bedrock -------------------------------
    # Return Bedrock settings when AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY
    # are both set. Guarding on them is what keeps this file runnable without
    # AWS -- do not drop the guard.
    #
    # Build the credentials first. session_token is STS-only, and it has to be
    # *absent* rather than None for long-lived IAM keys -- the SDK serializes
    # any field you pass explicitly, so session_token=None would put a literal
    # null on the wire alongside type="iam":
    #
    #   credentials = {
    #       "type": "sts" if AWS_SESSION_TOKEN else "iam",
    #       "region": AWS_REGION,
    #       "access_key_id": AWS_ACCESS_KEY_ID,
    #       "secret_access_key": AWS_SECRET_ACCESS_KEY,
    #   }
    #   if AWS_SESSION_TOKEN:
    #       credentials["session_token"] = AWS_SESSION_TOKEN
    #
    # Then two halves, and Bedrock needs both. Miss either and the handshake
    # fails:
    #
    #   provider=ThinkSettingsV1Provider_AwsBedrock(
    #       type="aws_bedrock",
    #       model=BEDROCK_MODEL,
    #       temperature=0.7,
    #       credentials=AwsBedrockThinkProviderCredentials(**credentials),
    #   ),
    #   endpoint=ThinkSettingsV1Endpoint(
    #       url=f"https://bedrock-runtime.{AWS_REGION}.amazonaws.com/",
    #   ),
    #
    # Keep prompt=PROMPT on it, or your agent loses the instruction that stops
    # it reading markdown aloud.
    #
    # The endpoint's region has to match the credentials' region. They are
    # written down twice here on purpose -- that mismatch is the second most
    # common way this step fails, after model access.
    # -----------------------------------------------------------------------
    return ThinkSettingsV1(
        provider=ThinkSettingsV1Provider_OpenAi(
            type="open_ai",
            model="gpt-4o-mini",
            temperature=0.7,
        ),
        prompt=PROMPT,
    )


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
        # The only line in SETTINGS that changes in this step. Everything about
        # which LLM answers, and whose account it runs in, is behind this call.
        think=think_settings(),
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
        # One report per turn, arriving right after the reply starts. Printed,
        # it buries the conversation -- Step 8 turns it on deliberately, once
        # there is a reason to read it. The browser shows the number either
        # way, on the right of the activity line above the transcript.
        pass
    elif message_type == "Error":
        # Where a refused Bedrock configuration lands. Unlike a misspelled voice
        # -- which warns and falls back -- there is nothing to fall back to when
        # the brain is rejected, so this one is fatal.
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
    which = "AWS Bedrock" if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY else "OpenAI (no AWS credentials in .env)"
    print(f">> Thinking with: {which}")
    bridge.run(settings=SETTINGS, on_message=on_message, on_media=on_media)


if __name__ == "__main__":
    main()
