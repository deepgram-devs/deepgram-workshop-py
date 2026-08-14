"""Step 7 - Function calling.

Runs exactly as Step 6 left it: a voice agent with your persona and voice.

Your job in this step is to turn it into a specialist. You will give it a
domain -- phone banking for Contoso Bank -- and then let it run Python, because
a banking agent that cannot look up a balance is just a chatbot with opinions
about money. You will advertise two functions in the agent's settings, handle
the FunctionCallRequest the agent sends when the LLM decides to use one, and
send the result back.

Look for the "TODO (Step 7.x)" blocks below and work through them in order.
Inside them, "#:" marks the instructions and everything else is code, commented
out at the indentation it belongs at: select those lines and press Cmd+/
(Ctrl+/ on Windows and Linux) to uncomment them where they sit.

Run it with:  uv run steps/07-function-calling/main.py
"""

#: ---- TODO (Step 7.1): Imports --------------------------------------------
#: You need three more imports for this step. Add them to the groups below,
#: keeping each group alphabetical:
#:
#:   standard library:
#:     import json                                 (parse the LLM's arguments,
#:                                                  and serialize your results)
#:
#:   third party:
#:     AgentV1SendFunctionCallResponse   -> into the deepgram.agent.v1.types
#:                                          block, first alphabetically
#:     from deepgram.types.think_settings_v1functions_item import (
#:         ThinkSettingsV1FunctionsItem,
#:     )
#: --------------------------------------------------------------------------

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

# Words this agent hears all day. Flux biases recognition toward them, which is
# the cheapest accuracy fix available for a domain-specific agent.
KEYTERMS = ["Contoso Bank", "routing number", "balance", "transaction"]

#: ---- TODO (Step 7.2): Write the functions --------------------------------
#: First, the data the agent will answer from. SYNTHETIC -- in production these
#: bodies call your core-banking API, server-side, behind your own auth. Two
#: accounts, keyed by their last four digits:
#:
# ACCOUNTS = {
#     "4821": {
#         "balance": 1250.40,
#         "transactions": [
#             {"date": "2026-03-03", "description": "Whole Foods Market", "amount": -84.12},
#             {"date": "2026-03-02", "description": "Payroll deposit, Contoso Inc", "amount": 2400.00},
#             {"date": "2026-03-01", "description": "Con Edison, utilities", "amount": -132.55},
#             {"date": "2026-02-27", "description": "Delta Air Lines", "amount": -412.30},
#         ],
#     },
#     "9007": {
#         "balance": 58.19,
#         "transactions": [
#             {"date": "2026-03-03", "description": "Starbucks", "amount": -6.75},
#             {"date": "2026-03-01", "description": "Venmo from A. Rivera", "amount": 40.00},
#             {"date": "2026-02-28", "description": "Spotify", "amount": -11.99},
#         ],
#     },
# }
#:
#:
#: Then a formatting helper. Format for the ear here, not in the prompt -- hand
#: the LLM "$1,250.40" and it reads it back correctly, hand it 1250.4 and you
#: will spend prompt tokens teaching it to say "dollars".
#:
# def usd(amount: float) -> str:
#:
#: Debits are negative, and the sign belongs outside the symbol: "-$84.12", not
#: "$-84.12", which is not something a person would say out loud.
#:
#: Then the two handlers. Both take the last four digits, both return a dict:
#:
# def lookup_balance(account_last_four: str) -> dict:
# def list_recent_transactions(account_last_four: str, limit: int = 3) -> dict:
#:
#: Look the account up with  ACCOUNTS.get(str(account_last_four)[-4:])  -- the
#: LLM may hand you the full number, or the digits with spaces in them.
#:
#: A miss RETURNS, it does not raise:
#:
#     {"found": False, "message": "No account found for those digits."}
#:
#: The agent turns that into a sentence. An exception leaves the caller
#: listening to silence.
#:
#: Then map the advertised names to the callables:
#:
# FUNCTION_HANDLERS = {
#     "lookup_balance": lookup_balance,
#     "list_recent_transactions": list_recent_transactions,
# }
#:
#: Docstrings are required here -- ruff is configured with pydocstyle (google).
#: --------------------------------------------------------------------------

#: ---- TODO (Step 7.3): Advertise the functions ----------------------------
#: Build the list the agent is told about. This is advertising only: the LLM
#: decides *whether* to call, your code decides *what happens* when it does.
#:
#: These declarations and the handlers above never reference each other. The
#: name string is the only thing joining them, which is worth remembering the
#: first time you rename one and not the other.
#:
# FUNCTIONS = [
#     ThinkSettingsV1FunctionsItem(
#         name="lookup_balance",
#         description=(
#             "Get the current balance for a customer account by its last "
#             "four digits. Use this whenever the customer asks how much "
#             "money they have."
#         ),
#         parameters={  # plain JSON Schema, as the LLM's tool API expects
#             "type": "object",
#             "properties": {
#                 "account_last_four": {
#                     "type": "string",
#                     "description": "The last 4 digits of the account number.",
#                 },
#             },
#             "required": ["account_last_four"],
#         },
#     ),
#     ThinkSettingsV1FunctionsItem(
#         name="list_recent_transactions",
#         description=(
#             "List the most recent transactions on an account, by its last "
#             "four digits. Use this for questions about spending, charges, "
#             "deposits, or recent activity."
#         ),
#         parameters={
#             "type": "object",
#             "properties": {
#                 "account_last_four": {
#                     "type": "string",
#                     "description": "The last 4 digits of the account number.",
#                 },
#                 "limit": {
#                     "type": "integer",
#                     "description": "How many transactions to return. Defaults to 3.",
#                 },
#             },
#             "required": ["account_last_four"],
#         },
#     ),
# ]
#:
#: The description is the prompt. It is the only thing the LLM reads when
#: deciding to call, so spell out *when* to use it, not just what it does.
#:
#: Note what is missing: "endpoint". Leaving it unset is what marks a function
#: client-side -- that is why Deepgram sends the call down the socket to you
#: instead of calling an HTTP endpoint itself.
#: --------------------------------------------------------------------------

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
                #: ---- TODO (Step 7.4a): Teach it the vocabulary -----------
                #: Add:  keyterms=KEYTERMS,
                #: ----------------------------------------------------------
            ),
        ),
        think=ThinkSettingsV1(
            provider=ThinkSettingsV1Provider_OpenAi(
                type="open_ai",
                model="gpt-4o-mini",
                #: ---- TODO (Step 7.4b): Cool it down ------------------------
                #: Drop temperature to 0.3. A banking agent should say the same
                #: thing twice when asked the same thing twice.
                #: ------------------------------------------------------------
                temperature=0.7,
            ),
            # The prompt is prepended to every user turn before it reaches the
            # LLM. It is the agent's standing instructions -- personality, job,
            # and boundaries. Keep it short: every token here is re-sent on
            # every turn, and long prompts slow the first reply.
            #: ---- TODO (Step 7.4c): Give it the job ---------------------
            #: Replace the neutral prompt below with the banking one. The
            #: NUMERIC DISCIPLINE block is the part that matters: it is what
            #: stops the agent inventing a balance, and it does that before
            #: you have written a single line of function-calling code.
            #:
            # prompt=(
            #     "You are a phone banking assistant for Contoso Bank. Be brief "
            #     "and clear -- the customer is listening, not reading. Never "
            #     "use markdown, bullet points, or emoji.\n"
            #     "\n"
            #     "NUMERIC DISCIPLINE:\n"
            #     "- When the customer gives you account digits, read them back "
            #     "one digit at a time to confirm before acting.\n"
            #     "- State money amounts in full ('one thousand two hundred "
            #     "fifty dollars and forty cents') and dates clearly ('March "
            #     "3rd, 2026').\n"
            #     "- NEVER invent a balance, a transaction, or any other "
            #     "number. If you do not have it, call a function or say you "
            #     "cannot find it.\n"
            #     "\n"
            #     "Use lookup_balance for balances and list_recent_transactions "
            #     "for recent activity. Ask for the last four digits of the "
            #     "account first."
            # ),
            #: ------------------------------------------------------------
            prompt=(
                "You are a helpful AI assistant. Keep your responses brief. "
                "You are speaking out loud, so never use markdown, bullet "
                "points, or emoji."
            ),
            #: ---- TODO (Step 7.4d): Attach the functions ------------------
            #: Add:  functions=FUNCTIONS,
            #: --------------------------------------------------------------
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
        #: ---- TODO (Step 7.4e): Open the call -------------------------------
        #: Replace the greeting below. This one sets the security expectation
        #: before the customer volunteers a full account number out loud:
        #:
        # greeting=(
        #     "Thanks for calling Contoso Bank. For your security I can only "
        #     "look things up by the last four digits of your account. How can "
        #     "I help?"
        # ),
        #: --------------------------------------------------------------------
        greeting="Hello! I'm a Deepgram voice agent. What would you like to talk about?",
    ),
)

#: ---- TODO (Step 7.5): Handle the call ------------------------------------
#: Write a module-level function:
#:
# def handle_function_call(agent: AgentHandle, message: object) -> None:
#:
#: A FunctionCallRequest carries a "functions" list. Loop over it; each entry has
#: .id, .name, and .arguments (a JSON *string*, not a dict). For each one:
#:
#:   1. Look the name up in FUNCTION_HANDLERS.
#:   2. Call it with  handler(**json.loads(arguments))
#:   3. Serialize the result:  content = json.dumps(result)
#:      `content` goes over the wire as a string, and your handlers return
#:      dicts. This is the line that joins them.
#:   4. Send it back:
#:
#:        agent.send_function_call_response(
#:            AgentV1SendFunctionCallResponse(id=call.id, name=name, content=content),
#:        )
#:
#: Two things that will bite you:
#:
#:   * Catch exceptions and return the error text as `content`. The agent is
#:     mid-turn and blocked waiting on you. A raised exception escapes into the
#:     SDK's receive loop, surfaces as EventType.ERROR, and drops the call.
#:
#:   * This runs on the SDK's receive loop -- the same thread delivering audio.
#:     A slow function stalls playback. Keep handlers fast, or hand the work to
#:     a thread and reply when it finishes. Routing audio through the browser
#:     does not change this: the bytes still pass through this thread on their
#:     way out.
#:
#: Print the call and the result. You want to see what the LLM actually passed.
#: --------------------------------------------------------------------------


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
    #: ---- TODO (Step 7.6): Dispatch the request ---------------------------
    #: Add a branch, above the LatencyReport one:
    #:
    # elif message_type == "FunctionCallRequest":
    #     handle_function_call(agent, message)
    #:
    #: Without it, the fallthrough at the bottom prints ">> FunctionCallRequest"
    #: and the agent waits forever for a reply that never comes -- a useful
    #: thing to see once on purpose.
    #: ----------------------------------------------------------------------
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
