"""Step 8 - Optimization.

Runs exactly as Step 7 left it: a complete phone banking agent that listens on
Flux, holds a conversation, yields the floor when interrupted, and answers from
your data by calling your Python.

Nothing is missing. What is left is how it *feels*, and that comes down to two
numbers that have been sitting in this file since Step 2 -- EOT_THRESHOLD and
EOT_TIMEOUT_MS, which decide when Flux calls your turn over. They are set to a
balanced default. Balanced is not the same as right for what you are building.

This step is dials rather than architecture, and it goes in the order any
optimization goes: measure first, then move something, then measure again.

Look for the "TODO (Step 8.x)" blocks below. Inside them, "#:" marks the
instructions and everything else is code, commented out at the indentation it
belongs at: select those lines and press Cmd+/ (Ctrl+/ on Windows and Linux) to
uncomment them where they sit.

Run it with:  uv run steps/08-optimize/main.py
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
# Audio is mono 16-bit signed PCM in both directions -- the most widely
# supported format across platforms and languages. The browser sends it in
# 80 ms chunks, the size Flux's turn detection is tuned for: smaller chunks add
# websocket overhead, larger ones delay turn detection. web/bridge.py derives
# that chunk size from SAMPLE_RATE, so this constant is the only place to change
# it.

#: ---- TODO (Step 8.2): Move the dials -------------------------------------
#: Flux scores every turn for end-of-turn confidence as the audio streams in.
#: These two constants act on that score, and they trade against each other:
#: end a turn too early and you cut people off mid-thought, too late and every
#: exchange carries a dead pause. There is no setting that avoids both.
#:
#: Once TODO 8.1 is printing a number, run the four rows in the LAB's table --
#: 0.5/5000, 0.9/5000, 0.7/500, then back to 0.7/5000 -- holding the same short
#: conversation each time. Listen, and watch ">> Latency:" alongside.
#:
#: A value outside its valid range does not fail the handshake. It comes back as
#: a Warning, which the branch you added in Step 6 prints. That is the payoff for
#: writing it: a threshold that seems to do nothing is usually a warning you can
#: now actually read.
#:
#: Also available: eager_eot_threshold (0.3-0.9, off by default, must be <=
#: EOT_THRESHOLD). It starts the LLM on a *probable* turn end and discards the
#: work if the user keeps talking -- lower latency, more LLM calls. Add it in the
#: provider below once the two constants make sense on their own.
#: --------------------------------------------------------------------------
EOT_THRESHOLD = 0.7  # Valid 0.5-0.9. Raise it to stop the agent cutting people off mid-thought, lower it for snappier replies at the cost of false turn ends.
EOT_TIMEOUT_MS = 5000  # Valid 500-60000. Hard ceiling: end the turn after this much silence, whatever the score says.


# Words this agent hears all day. Flux biases recognition toward them, which is
# the cheapest accuracy fix available for a domain-specific agent.
KEYTERMS = ["Contoso Bank", "routing number", "balance", "transaction"]

# SYNTHETIC account data, keyed by the last four digits of the account number.
# In production the handlers below call your core-banking API, server-side and
# behind your own auth. The agent never sees this code -- only the value you
# return, which it then reads to the customer.
ACCOUNTS = {
    "4821": {
        "balance": 1250.40,
        "transactions": [
            {"date": "2026-03-03", "description": "Whole Foods Market", "amount": -84.12},
            {"date": "2026-03-02", "description": "Payroll deposit, Contoso Inc", "amount": 2400.00},
            {"date": "2026-03-01", "description": "Con Edison, utilities", "amount": -132.55},
            {"date": "2026-02-27", "description": "Delta Air Lines", "amount": -412.30},
        ],
    },
    "9007": {
        "balance": 58.19,
        "transactions": [
            {"date": "2026-03-03", "description": "Starbucks", "amount": -6.75},
            {"date": "2026-03-01", "description": "Venmo from A. Rivera", "amount": 40.00},
            {"date": "2026-02-28", "description": "Spotify", "amount": -11.99},
        ],
    },
}


def usd(amount: float) -> str:
    """Format a dollar amount for the ear rather than for a screen.

    Formatting here instead of in the prompt is deliberate: hand the LLM
    "$1,250.40" and it reads it back correctly, hand it 1250.4 and you spend
    prompt tokens teaching it to say "dollars".

    Args:
        amount: A signed dollar amount. Debits are negative.

    Returns:
        The amount as a currency string, for example "$1,250.40" or "-$84.12".
        The sign goes outside the symbol -- "$-84.12" is not something a person
        would say.
    """
    sign = "-" if amount < 0 else ""
    return f"{sign}${abs(amount):,.2f}"


def lookup_balance(account_last_four: str) -> dict:
    """Return the current balance for one account.

    Args:
        account_last_four: The last 4 digits of the account number. The LLM
            sometimes passes the full number or digits with spaces in them, so
            only the last four are used.

    Returns:
        The balance and the date it is current as of, or a "not found" result.
        A miss returns rather than raises: the agent turns a returned message
        into a sentence, where an exception leaves the caller in silence.
    """
    account = ACCOUNTS.get(str(account_last_four)[-4:])
    if account is None:
        return {"found": False, "message": "No account found for those digits."}

    return {
        "found": True,
        "account_last_four": account_last_four,
        "balance": usd(account["balance"]),
        "as_of": "2026-03-03",
    }


def list_recent_transactions(account_last_four: str, limit: int = 3) -> dict:
    """Return the most recent transactions on one account.

    Args:
        account_last_four: The last 4 digits of the account number.
        limit: How many transactions to return, most recent first.

    Returns:
        The transactions with amounts pre-formatted as currency, or a "not
        found" result.
    """
    account = ACCOUNTS.get(str(account_last_four)[-4:])
    if account is None:
        return {"found": False, "message": "No account found for those digits."}

    return {
        "found": True,
        "account_last_four": account_last_four,
        "transactions": [
            {
                "date": transaction["date"],
                "description": transaction["description"],
                "amount": usd(transaction["amount"]),
                "type": "debit" if transaction["amount"] < 0 else "credit",
            }
            for transaction in account["transactions"][:limit]
        ],
    }


# Maps the function names advertised in FUNCTIONS to the Python that runs them.
# These two structures never reference each other -- the name string is the
# only thing joining them.
FUNCTION_HANDLERS = {
    "lookup_balance": lookup_balance,
    "list_recent_transactions": list_recent_transactions,
}

# What the agent is told it can call. This is advertising only: the LLM decides
# *whether* to call, this client decides *what happens* when it does. Leaving
# "endpoint" unset marks a function client-side, which is what makes Deepgram
# send a FunctionCallRequest down the socket and wait for our
# FunctionCallResponse rather than calling an HTTP endpoint itself.
FUNCTIONS = [
    ThinkSettingsV1FunctionsItem(
        name="lookup_balance",
        description=(
            "Get the current balance for a customer account by its last four "
            "digits. Use this whenever the customer asks how much money they "
            "have."
        ),
        # A JSON Schema object, exactly as the LLM's tool-calling API expects.
        parameters={
            "type": "object",
            "properties": {
                "account_last_four": {
                    "type": "string",
                    "description": "The last 4 digits of the account number.",
                },
            },
            "required": ["account_last_four"],
        },
    ),
    ThinkSettingsV1FunctionsItem(
        name="list_recent_transactions",
        description=(
            "List the most recent transactions on an account, by its last four "
            "digits. Use this for questions about spending, charges, deposits, "
            "or recent activity."
        ),
        parameters={
            "type": "object",
            "properties": {
                "account_last_four": {
                    "type": "string",
                    "description": "The last 4 digits of the account number.",
                },
                "limit": {
                    "type": "integer",
                    "description": "How many transactions to return. Defaults to 3.",
                },
            },
            "required": ["account_last_four"],
        },
    ),
]

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
                keyterms=KEYTERMS,  # Bias recognition toward the words this domain repeats.
            ),
        ),
        think=ThinkSettingsV1(
            provider=ThinkSettingsV1Provider_OpenAi(
                type="open_ai",
                model="gpt-4o-mini",
                temperature=0.3,  # A banking agent should say the same thing twice when asked the same thing twice.
            ),
            # The prompt is prepended to every user turn before it reaches the
            # LLM. It is the agent's standing instructions -- personality, job,
            # and boundaries. Keep it short: every token here is re-sent on
            # every turn, and long prompts slow the first reply.
            prompt=(
                "You are a phone banking assistant for Contoso Bank. Be brief "
                "and clear -- the customer is listening, not reading. Never "
                "use markdown, bullet points, or emoji.\n"
                "\n"
                "NUMERIC DISCIPLINE:\n"
                "- When the customer gives you account digits, read them back "
                "one digit at a time to confirm before acting.\n"
                "- State money amounts in full ('one thousand two hundred "
                "fifty dollars and forty cents') and dates clearly ('March "
                "3rd, 2026').\n"
                "- NEVER invent a balance, a transaction, or any other "
                "number. If you do not have it, call a function or say you "
                "cannot find it.\n"
                "\n"
                "Use lookup_balance for balances and list_recent_transactions "
                "for recent activity. Ask for the last four digits of the "
                "account first."
            ),
            functions=FUNCTIONS,
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
        greeting=(
            "Thanks for calling Contoso Bank. For your security I can only "
            "look things up by the last four digits of your account. How can "
            "I help?"
        ),
    ),
)


def handle_function_call(agent: AgentHandle, message: object) -> None:
    """Run every client-side function the agent asked for and return the results.

    The agent is mid-turn and blocked on these responses, so failures are
    reported back as the function's result rather than raised. A raised
    exception would escape into the SDK's receive loop, surface as
    EventType.ERROR, and drop the call.

    This runs on the SDK's receive loop thread, which is also the thread
    delivering audio. A slow function here stalls playback for everyone. Keep
    handlers fast, or hand the work to a thread and reply once it finishes.

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
                # content goes over the wire as a string; the handlers return dicts.
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

    Unrecognized message types fall through to a plain print so that new server
    events stay visible rather than being silently dropped.

    Args:
        agent: The connected agent, used to reply to function calls.
        player: Where audio is played. send() queues a chunk, clear() throws
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
        # clear() throws both away. Nothing about that queue is worth keeping:
        # every byte in it was produced before the user opened their mouth.
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
        # One report per turn, arriving right after the reply starts.
        #: ---- TODO (Step 8.1): Measure before you tune --------------------
        #: Uncomment the three lines below. total_latency is end-of-utterance to
        #: first audio byte -- the exact number the knobs in TODO 8.2 move, and
        #: the only honest way to tell whether a change helped. Everything else
        #: is impression.
        #:
        #: The report also carries ttt_token_latency, ttt_text_latency,
        #: ttt_tool_latency, ttt_thinking_latency, and tts_latency. Every field
        #: is optional -- absent, not zero, when it does not apply, which is why
        #: the None check below is not decoration.
        #:
        #: The browser has been showing this number all along, on the right of
        #: the activity line above the transcript. Watching it move while you
        #: talk is a faster feedback loop than reading the console; the print is
        #: what lets you keep a record across runs.
        #: ------------------------------------------------------------------
        # total = getattr(message, "total_latency", None)
        # if total is not None:
        #     print(f">> Latency: {total:.2f}s")
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
    """Serve the page and stream audio until interrupted.

    Everything about connection order lives in web/bridge.py: it waits for the
    browser's speaker before opening the Deepgram socket, and waits for the
    settings handshake before letting the microphone send anything. The agent
    discards media until that handshake completes, so the order matters.
    """
    bridge.run(settings=SETTINGS, on_message=on_message, on_media=on_media)


if __name__ == "__main__":
    main()
