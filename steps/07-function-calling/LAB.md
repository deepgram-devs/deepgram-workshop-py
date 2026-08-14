# Step 7: Function calling

**Goal:** Turn the agent into a specialist that answers from your data instead of from its imagination.

**You'll learn**

- What makes a function client-side, and why that's a single omitted field
- Why the function description *is* a prompt
- The threading trap that turns a slow function into stuttering audio

## Start here

```bash
uv run steps/07-function-calling/main.py
```

You have a complete voice agent. Tell it you're calling about your bank account and ask for your balance. It will give you a number: confident, specific, and completely fabricated, because a language model has no database. This step closes that gap and every gap like it.

By the end of it you'll have a phone banking agent for Contoso Bank that looks up real balances and reads back real transactions. Banking is the scenario because it punishes vagueness: a support bot that paraphrases is annoying, a banking bot that paraphrases is a problem. Every rule you write here transfers to whatever domain you actually work in.

## The mental model

Function calling connects the agent to things the model can't know: your database, your API, the current time, the user's order history. The flow has four hops.

1. You advertise a function in `SETTINGS`: name, description, and a JSON Schema for its parameters.
2. The LLM decides a user turn warrants calling it, and Deepgram sends you a `FunctionCallRequest`.
3. Your code runs the function and sends back a `FunctionCallResponse`.
4. The LLM works your result into its reply, and the agent speaks it.

The single most important detail: **leaving `endpoint` unset marks a function client-side.** That one omission makes Deepgram send the call down the socket to you, instead of calling an HTTP endpoint itself. Set `endpoint` and Deepgram handles the call server-side and you never see it. Both are valid; client-side is what you want when the function touches local state, local credentials, or anything you'd rather not expose over HTTP. It also means you need no public URL and no tunnel to finish this step.

> **Check yourself:** What single change to the function definition moves execution from your machine to Deepgram's?

The second most important detail: **the description is a prompt.** It's the only thing the LLM reads when deciding whether to call your function. Write it to say *when* to use the function, not just what it does. "Get the balance" is worse than "Get the current balance for a customer account by its last four digits. Use this whenever the customer asks how much money they have."

### The two halves of a function

Every function you write lives in two places that never reference each other. The name string is the only thing joining them.

**The declaration** goes in `FUNCTIONS`, carrying a name, a description, and a JSON Schema for the arguments. This is what the LLM sees, and it's *all* the LLM sees. It never sees your implementation.

**The implementation** goes in `FUNCTION_HANDLERS`, registered under exactly that name. It receives whatever arguments the LLM chose and returns a value the agent will read aloud.

Keep that split in mind, because it explains the most common failure in this step: rename one and not the other, and you get an agent that decides to call something, waits, and then apologizes for a problem it can't describe.

### Guard it in prose first

The banking prompt you're about to write carries a NUMERIC DISCIPLINE block, and one line in it does more work than the rest:

```
NEVER invent a balance, a transaction, or any other number.
```

That rule closes the fabrication gap before a single line of function-calling code exists. A model with no data and no instruction covering the gap fills it, confidently. Write the guardrail in prose, then give it the function that makes obeying the guardrail possible.

> **⏸ Pause: check in with the instructor**
> Before writing code, sketch a function for your *own* use case. What would your agent need to look up that the model cannot know? Share one or two with the room.

## Do this

**TODO 7.1: Add the imports.** Three of them, listed in the file.

**TODO 7.2: Write the functions.** The `ACCOUNTS` data, a `usd()` helper, then `lookup_balance` and `list_recent_transactions`.

Two habits to copy from these handlers, because they're what separates a handler that demos from one that ships.

**Format for the ear.** `usd()` returns `"$1,250.40"`, not `1250.4`. Hand the LLM a shape it can read aloud and you spend fewer prompt tokens on formatting rules, with fewer chances for it to say "one thousand two hundred fifty point four."

**Return a graceful miss, don't raise.** A missing account returns `{"found": False, "message": "No account found for those digits."}`. The agent turns that into a sentence. An exception leaves the caller listening to silence.

**TODO 7.3: Advertise them.** Build the `FUNCTIONS` list. The `parameters` field is plain JSON Schema, exactly as the LLM's tool-calling API expects.

**TODO 7.4: Make it a banking agent.** Five small edits in `SETTINGS`: `keyterms`, temperature, the prompt, `functions=FUNCTIONS`, and the greeting.

`keyterms` biases Flux toward the words this domain repeats all day. It's the highest-leverage accuracy fix for a domain agent and it costs one line. Note that Flux has no `numerals` or `smart_format` parameter; those belong to the v1 Listen API. On Flux, spoken-number accuracy comes from `keyterms` plus the prompt rule that makes the agent read digits back before acting on them, which is a better habit anyway.

**TODO 7.5: Handle the call.** Write `handle_function_call`. Three things will bite you here:

**`content` is a string.** Your handlers return dicts, so `json.dumps` the result on the way out.

**Catch exceptions and return the error text as `content`.** The agent is mid-turn and blocked waiting on your response. A raised exception escapes into the SDK's receive loop, surfaces as `EventType.ERROR`, and drops the call. Returning `"lookup_balance failed: ..."` lets the LLM apologize gracefully and move on.

**This runs on the SDK's receive loop, the same thread delivering audio.** A slow function stalls playback for the whole conversation. Keep handlers fast, or hand the work to a thread and reply when it finishes. This is a real production failure mode, not a workshop artifact, and it's the reason a real balance lookup belongs behind a timeout.

Print both the call and the result. You want to see what the LLM actually passed you.

**TODO 7.6: Dispatch it.** Add the `FunctionCallRequest` branch.

Run it *before* you add this branch, once. You'll see `>> FunctionCallRequest` from the fallthrough and then nothing. The agent waits forever for a reply that never comes. Worth seeing on purpose, because it's what a broken handler looks like from the outside.

## Verify

Connect and work down this script:

1. *"What's the balance on the account ending 4821?"* → **$1,250.40**
2. *"Read me the last three transactions."* → itemized, clean currency and dates
3. *"What about the account ending 9007?"* → a second account, **$58.19**
4. *"Try account 1111."* → the not-found path, spoken gracefully

The console shows both halves of each call:

```
[user] What's the balance on the account ending 4821?
>> Function call: lookup_balance({"account_last_four":"4821"})
>> Function result: {"found": true, "account_last_four": "4821", "balance": "$1,250.40", "as_of": "2026-03-03"}
>> Agent thinking...
[assistant] That account has a balance of one thousand two hundred fifty dollars and forty cents, as of March 3rd.
```

Notice the agent read your digits back before it acted on them. That's the prompt, not the code.

Then ask it something that shouldn't trigger a call ("what's the capital of France?") and confirm no function fires. An agent that calls functions it doesn't need is as broken as one that never calls them.

### Test data

| Say | Result |
|---|---|
| account `4821` | balance $1,250.40, 4 transactions |
| account `9007` | balance $58.19, 3 transactions |
| anything else | the graceful not-found path |

## Stuck?

**The function never gets called.** Nine times out of ten it's the description. Make it explicit about *when* to use the function. Confirm `functions=FUNCTIONS` actually reached `ThinkSettingsV1`.

**The agent apologizes vaguely and the console shows the call.** The name in `FUNCTIONS` doesn't match the key in `FUNCTION_HANDLERS`. The two halves only meet through that string.

**`>> FunctionCallRequest` prints and the agent goes silent.** TODO 7.6 isn't done, or your handler raised before sending a response. The agent is still waiting.

**`TypeError: got an unexpected keyword argument`.** The LLM passed a parameter your Python doesn't accept. Your schema and your signature have drifted apart.

**The agent interrogates the caller for things it could infer.** Too many properties marked `required`. Require only what you can't proceed without.

**Audio stutters when a function runs.** The threading trap. Your handler is too slow for the receive loop.

**Agent gets the answer but says something different.** The LLM paraphrases your result. Return clear, pre-formatted values and it stays close to them.

**The account digits come through wrong.** Check `keyterms` reached the listen provider, and confirm the prompt still tells the agent to read digits back. That read-back is your last line of defense against a misheard four.

`steps/08-optimize/main.py` is this step, finished.

## The recipe for any function

The banking scenario is scaffolding. This is the part that transfers:

1. **Name it after the action.** `lookup_balance` beats `get_data`. The name steers the model nearly as much as the description does.
2. **Declare it** with no `endpoint`, so your code runs it.
3. **Describe when to call it**, not just what it does. Descriptions steer behavior.
4. **Implement it** under exactly that name. Validate inputs, return graceful misses instead of throwing, and return only what the agent may say out loud.
5. **Reference it in the prompt** when calling it should be mandatory rather than optional.

Then test by voice, including the paths where it fails.

## Going further

**Add `transfer_funds`.** Reading data gets you halfway. Moving money introduces a confirmation step, which is where voice agents get interesting.

```python
def transfer_funds(from_last_four: str, to_last_four: str, amount: float) -> dict:
    """Move money between two accounts, after the customer has confirmed it."""
    source = ACCOUNTS.get(str(from_last_four)[-4:])
    target = ACCOUNTS.get(str(to_last_four)[-4:])
    if source is None or target is None:
        return {"ok": False, "message": "I could not find one of those accounts."}

    # Validate before mutating. The LLM will send you a string, a negative, or
    # an amount larger than the balance, and it will do it this week.
    value = float(amount)
    if value <= 0:
        return {"ok": False, "message": "That is not a valid transfer amount."}
    if value > source["balance"]:
        return {"ok": False, "message": f"Insufficient funds. That account holds {usd(source['balance'])}."}

    source["balance"] -= value
    target["balance"] += value
    return {"ok": True, "transferred": usd(value), "from_balance": usd(source["balance"])}
```

Declare it with a description that carries an instruction, not just a definition:

> "Move money between two of the customer's accounts. Only call this after the customer has confirmed the amount and both accounts out loud."

Then back that up in the prompt's NUMERIC DISCIPLINE block:

> "Before calling transfer_funds, repeat the amount and both accounts back and wait for the customer to say yes. Never transfer on an implied request."

Say *"move fifty dollars from the account ending 4821 to the one ending 9007."* The agent should read the transfer back and wait for you. Ask for the 4821 balance afterward to hear $1,200.40. The mutation persists for the life of the process.

Then go break it. Ask to move five thousand dollars, then name an account that doesn't exist. Your production handler meets both in its first week, and both read better as a returned message than as a thrown exception.

**Stretch:** right now the confirmation lives entirely in the prompt, so a determined caller can talk past it. Move the guarantee into code: have `transfer_funds` return a `pending_confirmation` token that a second `confirm_transfer` call has to present. Real money movement works this way, and prompts are not an authorization layer.

**Optional detour:** [Step 7b](../07b-healthcare/LAB.md) applies the same machinery to a clinic scheduling agent, where the interesting problem is the opposite one: what the agent must never repeat aloud. Fifteen minutes, no extra credentials, and it's where the payload-filtering habit gets taught properly.

---

You've built a complete voice agent: it listens on Flux, thinks with an LLM, speaks with Flux TTS, yields the floor when interrupted, and answers from your data instead of its own imagination. Nothing is missing.

What's left is how it feels, and that comes down to two numbers you haven't touched yet.

**Next:** [Step 8: Optimization](../08-optimize/LAB.md)
