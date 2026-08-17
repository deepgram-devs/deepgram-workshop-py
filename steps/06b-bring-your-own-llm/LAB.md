# Step 6b: Bring your own LLM (optional)

> **Optional, and it needs something you may not have.** This step runs the agent's brain on Amazon Bedrock, in *your* AWS account. That means AWS credentials with Bedrock access, and Bedrock grants model access per model **and** per region.
>
> This step shows how Deepgram's SDK supports the AWS ecosystem. Step 7 continues from Step 6 with or without AWS, and `main.py` here falls back to OpenAI when there are no AWS credentials in `.env`, so it runs regardless.

**Goal:** Move the LLM dependency from Deepgram's managed provider to your own hosted model in AWS Bedrock.

**You'll learn**

- Which think providers Deepgram brokers for you, and which ones it doesn't
- What `think.endpoint` is for, and why it's the setting that matters beyond Bedrock
- Where your AWS secret actually travels, and how to scope it accordingly

## Start here

```bash
uv run steps/06b-bring-your-own-llm/main.py
```

It prints which brain it's using before it opens the browser:

```
>> Thinking with: OpenAI (no AWS credentials in .env)
```

That's the same agent Step 6 finished with (neutral prompt, neutral voice), and it will keep working exactly like that until you put AWS credentials in `.env`.

## How it works

Every step so far has needed one credential. `.env` has held a single Deepgram key, and that key has paid for speech-to-text, the LLM, and text-to-speech alike. Step 6 let you swap `gpt-4o-mini` for `gpt-4o` without so much as an OpenAI account.

That convenience comes from a split in the provider list:

**Brokered by Deepgram:** OpenAI, Anthropic, Google, NVIDIA. Deepgram holds the account, makes the call, and bills you. You name a model and you're done.

**Bring your own:** Groq and AWS Bedrock. Deepgram makes the call *as you*, with credentials you hand it, against an endpoint you name. Your account, your model access, your bill.

The second group is the interesting one, because it's the answer to a question that comes up the moment a voice agent stops being a demo: *can the model run somewhere I control?* A regulated industry, a model you've fine-tuned, a negotiated rate you'd rather keep. All of it lands here.

Two settings carry it, and Bedrock needs **both**:

**`think.provider`:** which model, and the credentials to reach it. `ThinkSettingsV1Provider_AwsBedrock` takes either long-lived `iam` keys or short-lived `sts` ones, which additionally carry a `session_token`.

**`think.endpoint`:** the URL Deepgram sends the completion request to. For Bedrock that's `https://bedrock-runtime.{region}.amazonaws.com/`, and the region has to match the one in your credentials.

`endpoint` is the setting worth remembering after today. It isn't Bedrock-specific: point it at anything that speaks the OpenAI Chat Completions format (a self-hosted model, a gateway in front of your own inference, a router) and the agent talks to it. Bedrock is just the case with enough structure that Deepgram gave it a provider type of its own.

**One thing to be clear-eyed about.** Your AWS access key and secret go into the `Settings` message, over the WebSocket, to Deepgram. That is what "Deepgram makes the call as you" means. So don't hand it your root credentials or an admin user. Create an IAM user scoped to `bedrock:InvokeModelWithResponseStream` on the one model ARN you're using, or issue short-lived STS credentials. The blast radius of a workshop credential should be one model in one region.

> **Check yourself:** Step 6 let you switch to `gpt-4o` with nothing but a model name. Why does Bedrock need two settings and a second credential?

## Do this

First, get the credentials into `.env`. `.env.example` has the block, commented and at the bottom. Copy it across and fill in:

```bash
AWS_REGION=us-east-2
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
```

Then enable model access for `zai.glm-4.7-flash` in that region, at [Bedrock → Model access](https://console.aws.amazon.com/bedrock/home#/modelaccess). Access is per model and per region, so enabling it in `us-east-1` does nothing for an agent pointed at `us-east-2`. Some model families also want a one-time use case form, which is not instant.

**If you already did the Pipecat edition of this workshop, note what does *not* carry over:** `AWS_BEARER_TOKEN_BEDROCK` is a botocore convenience, and there's no botocore here. Deepgram takes an access key and secret, or STS credentials, and nothing else.

Now the code. All three TODOs sit where their code goes, and each carries its own guidance, so you shouldn't need to scroll between an instruction and the line it's about.

**TODO 6b.1: Uncomment the imports.** Three of them, already sited at their alphabetical places in the import block (`6b.1a` through `6b.1c`).

**TODO 6b.2: Guard, then build the credentials.** In `think_settings()`, above the fallback `return`. Guard on `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`, then build the credentials as a plain dict.

Keep the guard. It's what lets the person next to you, who never got model access approved, run your file.

And build the credentials as a dict rather than passing keyword arguments, so `session_token` can be *absent* for long-lived IAM keys. The SDK serializes any field you pass explicitly, so `session_token=None` would put a literal `null` on the wire next to `type="iam"`.

**TODO 6b.3: Return the Bedrock settings.** Still inside the guard: `provider`, `endpoint`, and `prompt`. Bedrock needs the first two together (miss either and the handshake fails), and the region appears in both.

Note what `model` is doing here: Bedrock model IDs pass through to AWS untouched. The SDK's type hints list two Claude 3.5 IDs and then accept any string, so nothing catches a typo locally. A wrong model ID comes back from AWS at handshake time, not from your editor.

Once Bedrock answers, set `AWS_BEDROCK_MODEL` in `.env` to another model you enabled and listen for what a different brain does to latency and voice.

## Verify

```
>> Thinking with: AWS Bedrock
>> Settings applied
```

Then hold a conversation. It should be indistinguishable from Step 6's agent, because it is: same prompt, same voice, different account paying for the tokens.

Now check the bill you just moved: the request shows up in **AWS → Bedrock → Usage**, and nowhere in your Deepgram console. Speech-to-text and text-to-speech are still Deepgram's; only the middle of the pipeline changed hands.

> **⏸ Pause: check in with the instructor**
> If the room is on this step at all, it's worth asking out loud how many people got model access approved. That number is the whole story of whether bring-your-own is a realistic default for a team.

## Stuck?

**`>> Agent error: ...` and the agent never speaks.** Unlike a misspelled voice, a refused brain is fatal. There's nothing to fall back to, so it errors rather than warns. Read the description; it usually names which of the four things below went wrong.

**Model access is not enabled.** The most common failure by a wide margin, and the slowest to fix. Enable the exact model ID, in the exact region, at [Bedrock → Model access](https://console.aws.amazon.com/bedrock/home#/modelaccess).

**Region mismatch.** `AWS_REGION` feeds both the credentials and the endpoint URL, so they can't disagree in the shipped code. If you hardcoded either one while experimenting, that's the first thing to check.

**Credentials rejected.** Confirm the IAM user can actually invoke Bedrock. `bedrock:InvokeModelWithResponseStream` is the permission the agent needs; `bedrock:InvokeModel` alone is not enough, because the agent streams.

**`Thinking with: OpenAI (AWS credentials are in .env, but think_settings() is not using them yet)`.** Your keys are fine; the code isn't wired up. That line reports what `think_settings()` actually returned rather than what's in your environment, so it says this until TODO 6b.2 and 6b.3 are both done.

**It says `Thinking with: OpenAI (no AWS credentials in .env)` and you're sure the keys are set.** `.env` is read by `load_dotenv()` at import. A key set only in your shell for a previous command won't be there. Check for a stray space after the `=`.

Here's the finished `think_settings()`, since there's no next folder to check against. This step is a detour, and Step 7 picks up from Step 6:

```python
def think_settings() -> ThinkSettingsV1:
    """Build the think settings, on Bedrock when AWS credentials are present.

    Returns:
        The think settings the agent is configured with.
    """
    if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
        credentials = {
            "type": "sts" if AWS_SESSION_TOKEN else "iam",
            "region": AWS_REGION,
            "access_key_id": AWS_ACCESS_KEY_ID,
            "secret_access_key": AWS_SECRET_ACCESS_KEY,
        }
        if AWS_SESSION_TOKEN:
            credentials["session_token"] = AWS_SESSION_TOKEN

        return ThinkSettingsV1(
            provider=ThinkSettingsV1Provider_AwsBedrock(
                type="aws_bedrock",
                model=BEDROCK_MODEL,
                temperature=0.7,
                credentials=AwsBedrockThinkProviderCredentials(**credentials),
            ),
            endpoint=ThinkSettingsV1Endpoint(
                url=f"https://bedrock-runtime.{AWS_REGION}.amazonaws.com/",
            ),
            prompt=PROMPT,
        )

    return ThinkSettingsV1(
        provider=ThinkSettingsV1Provider_OpenAi(
            type="open_ai",
            model="gpt-4o-mini",
            temperature=0.7,
        ),
        prompt=PROMPT,
    )
```

## Going further

Try the other half of the idea. Leave `provider` set to `open_ai` and point `endpoint` at an OpenAI-compatible gateway of your own: a local server, a proxy that logs every completion, a router across several models. That's `think.endpoint` doing the thing it's actually for, and it's how you'd put a Bedrock Agent, request logging, or a header rewrite in front of the model.

---

Your agent's brain can now live wherever you need it to. Back to the main line. What it still can't do is anything outside its own head.

**Next:** [Step 7: Function calling](../07-function-calling/LAB.md)
