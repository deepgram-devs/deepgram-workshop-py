"""Step 7b - A second vertical: healthcare (optional).

WARNING: a demo, not a HIPAA-compliant system. Every record below is invented.
Do not put real patient data into this file.

Optional, and it is not a link in the chain -- Step 8 continues from Step 7
either way. Unlike Step 6b it needs no credential beyond your Deepgram key, so
it costs you about fifteen minutes and nothing else.

Step 7 built a banking agent. This one is a clinic scheduling agent, and it
carries the two lessons banking does not: teaching Flux a vocabulary it has
never heard, and holding back data the agent must never say out loud. The
function-calling machinery arrives already written -- handle_function_call and
its dispatch branch are exactly what you wrote in Step 7. You only touch what
is new to this track.

Work through the "TODO (Step 7b.x)" blocks below in order. Inside them, "#:"
marks the instructions and everything else is code, commented out at the
indentation it belongs at: select those lines and press Cmd+/ (Ctrl+/ on
Windows and Linux) to uncomment them where they sit.

Run it with:  uv run steps/07b-healthcare/main.py
"""

import json

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

# Flux's turn detection knobs, at the same balanced starting point as Step 7.
EOT_THRESHOLD = 0.7  # Valid 0.5-0.9. Raise it to stop the agent cutting people off mid-thought, lower it for snappier replies at the cost of false turn ends.
EOT_TIMEOUT_MS = 5000  # Valid 500-60000. Hard ceiling: end the turn after this much silence, whatever the score says.

#: ---- TODO (Step 7b.1): Teach it the clinic's vocabulary ------------------
#: Leave this list EMPTY for the first run. Connect, and say:
#:
#:   "I'm calling about my semaglutide prescription with Doctor Bergstrom."
#:
#: Read what lands in the transcript. A general model has no reason to know
#: those words, and it will guess at something that sounds close.
#:
#: Then fill the list, restart, and say the same sentence again:
#:
# KEYTERMS = [
#     "Ozempic",
#     "semaglutide",
#     "metformin",
#     "lisinopril",
#     "atorvastatin",
#     "colonoscopy",
#     "echocardiogram",
#     "A1C",
#     "Dr. Nwosu",
#     "Dr. Bergstrom",
# ]
#:
#: One line of configuration buys accuracy on the vocabulary your domain
#: repeats all day: drug names, procedures, proper nouns, SKUs. Whatever your
#: users say that the internet at large does not.
#: --------------------------------------------------------------------------
KEYTERMS: list[str] = []

# SYNTHETIC patient records, keyed by "firstname:id_last_four". In production
# this is a call to your EHR or scheduling system, server-side, behind your own
# auth and audit logging.
#
# Note what these records hold that the agent must never say: a full date of
# birth, a full patient ID, a phone number. They are here on purpose -- Step
# 7b.3 is about what you do with data you are allowed to look up but not
# allowed to repeat.
PATIENTS = {
    "maria:1234": {
        "first_name": "Maria",
        "date_of_birth": "1978-04-02",
        "patient_id": "LFH-000-1234",
        "phone": "555-0147",
        "next_appointment": {
            "date": "2026-08-12",
            "time": "9:30 AM",
            "provider": "Dr. Nwosu",
            "type": "A1C follow-up",
            "location": "Lakeside Family Health, Suite 200",
        },
    },
    "james:5678": {
        "first_name": "James",
        "date_of_birth": "1965-11-20",
        "patient_id": "LFH-000-5678",
        "phone": "555-0192",
        "next_appointment": {
            "date": "2026-08-19",
            "time": "2:00 PM",
            "provider": "Dr. Bergstrom",
            "type": "Echocardiogram",
            "location": "Lakeside Cardiology, 3rd floor",
        },
    },
}


def patient_key(first_name: str, patient_id_last_four: str) -> str:
    """Build the PATIENTS lookup key from what the caller said out loud.

    Args:
        first_name: The patient's first name, in whatever case Flux heard it.
        patient_id_last_four: The last 4 digits of the patient ID. The LLM may
            hand over the full ID, so only the last four are used.

    Returns:
        A "firstname:1234" key, lowercased and trimmed.
    """
    return f"{str(first_name).strip().lower()}:{str(patient_id_last_four)[-4:]}"


#: ---- TODO (Step 7b.3): Return only what the agent may speak --------------
#: Write the handler:
#:
# def find_appointment(first_name: str, patient_id_last_four: str) -> dict:
#:
#: Look the patient up with  PATIENTS.get(patient_key(first_name, patient_id_last_four))
#: and return a graceful miss when there isn't one:
#:
#     {"verified": False, "message": "I could not verify a patient with that name and ID."}
#:
#: Then -- and this is the whole point of the step -- return only three keys:
#:
#     {
#         "verified": True,
#         "first_name": patient["first_name"],
#         "next_appointment": patient["next_appointment"],
#     }
#:
#: The tempting version is  return patient. It works, it is shorter, and it
#: hands the LLM a date of birth, a full patient ID, and a phone number.
#:
#: The prompt in 7b.2 tells the agent not to speak those. The payload is what
#: makes speaking them impossible. Treat the payload as the enforcement layer
#: and the prompt as backup, because the model may say anything you hand it.
#: Filter at the boundary.
#:
#: Then register it, replacing the empty dict below:
#:
# FUNCTION_HANDLERS = {"find_appointment": find_appointment}
#: --------------------------------------------------------------------------

# Empty until TODO 7b.3. Until then the agent advertises a function nobody
# implements, hears back "No function named 'find_appointment' is available",
# and apologizes -- which is what a handler you forgot to register sounds like
# from the caller's side. Worth hearing once.
FUNCTION_HANDLERS: dict = {}

FUNCTIONS = [
    ThinkSettingsV1FunctionsItem(
        name="find_appointment",
        description=(
            "Find a patient's next appointment, once their identity is "
            "confirmed. Requires their first name and the last four digits of "
            "their patient ID."
        ),
        parameters={
            "type": "object",
            "properties": {
                "first_name": {
                    "type": "string",
                    "description": "The patient's first name.",
                },
                "patient_id_last_four": {
                    "type": "string",
                    "description": "The last 4 digits of the patient ID.",
                },
            },
            "required": ["first_name", "patient_id_last_four"],
        },
    ),
]

SETTINGS = AgentV1Settings(
    audio=AgentV1SettingsAudio(
        input=AgentV1SettingsAudioInput(encoding="linear16", sample_rate=SAMPLE_RATE),
        output=AgentV1SettingsAudioOutput(encoding="linear16", sample_rate=SAMPLE_RATE),
    ),
    agent=AgentV1SettingsAgent(
        listen=AgentV1SettingsAgentContextListen(
            provider=AgentV1SettingsAgentContextListenProvider_V2(
                type="deepgram",
                model="flux-general-en",
                eot_threshold=EOT_THRESHOLD,
                eot_timeout_ms=EOT_TIMEOUT_MS,
                # Empty until you fill it in TODO 7b.1, which is the point:
                # run it once without, and once with.
                keyterms=KEYTERMS,
            ),
        ),
        think=ThinkSettingsV1(
            provider=ThinkSettingsV1Provider_OpenAi(
                type="open_ai",
                model="gpt-4o-mini",
                temperature=0.3,
            ),
            #: ---- TODO (Step 7b.2): Write the privacy guardrails ----------
            #: Replace the placeholder prompt below. The PRIVACY GUARDRAILS
            #: block is the part that matters -- it is a scheduling agent that
            #: has to be useful without ever confirming who somebody is to
            #: anyone who happens to be holding their phone.
            #:
            # prompt=(
            #     "You are a scheduling assistant for Lakeside Family Health. "
            #     "Be warm, brief, and clear. You are speaking out loud, so "
            #     "never use markdown, bullet points, or emoji.\n"
            #     "\n"
            #     "PRIVACY GUARDRAILS:\n"
            #     "- Verify identity using ONLY the patient's first name and "
            #     "the last four digits of their patient ID. Never ask for a "
            #     "full SSN.\n"
            #     "- NEVER read a full date of birth, full patient ID, or full "
            #     "phone number aloud. Refer to 'the ID ending in 1-2-3-4'.\n"
            #     "- Do not give clinical or medication advice. For medical "
            #     "questions, offer to have a nurse call back.\n"
            #     "\n"
            #     "Use find_appointment to look up a patient's next visit once "
            #     "their identity is confirmed."
            # ),
            #: --------------------------------------------------------------
            prompt=(
                "You are a helpful AI assistant. Keep your responses brief. "
                "You are speaking out loud, so never use markdown, bullet "
                "points, or emoji."
            ),
            functions=FUNCTIONS,
        ),
        speak=SpeakSettingsV1(
            provider=SpeakSettingsV1Provider_Deepgram(
                type="deepgram",
                model="flux-alexis-en",
            ),
        ),
        # Identity first, so verification happens before anything else does.
        greeting=(
            "Thank you for calling Lakeside Family Health. To pull up your "
            "record, can I get your first name and the last four digits of "
            "your patient ID?"
        ),
    ),
)


def handle_function_call(agent: AgentHandle, message: object) -> None:
    """Run every client-side function the agent asked for and return the results.

    Unchanged from Step 7. The agent is mid-turn and blocked on these
    responses, so failures are reported back as the function's result rather
    than raised, and this runs on the SDK's receive loop thread, which is also
    the thread delivering audio.

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
                content = json.dumps(handler(**json.loads(arguments)))
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
        pass
    elif message_type == "Error":
        code = getattr(message, "code", "unknown")
        description = getattr(message, "description", "unknown error")
        print(f">> Agent error: {code} - {description}")
    elif message_type == "Warning":
        code = getattr(message, "code", "unknown")
        description = getattr(message, "description", "unknown warning")
        print(f">> Agent warning: {code} - {description}")
    else:
        print(f">> {message_type}")


def on_media(agent: AgentHandle, audio: bytes) -> None:
    """Forward one captured chunk of microphone audio to the agent.

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
