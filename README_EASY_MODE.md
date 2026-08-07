# Easy Mode — the workshop without the code

Build and tune a voice agent in your browser, with nothing installed. No Python, no terminal, no API key pasted into a file. If you have a browser and a microphone, you can do every conceptual exercise in this workshop and end up with a configuration you can hand to a developer — or take into the code track later.

This track runs on the [Deepgram Playground](https://playground.deepgram.com/voice-agent). It's the same Voice Agent API the Python track talks to. The playground just puts a form in front of it.

**This track is for you if** you came to understand voice agents rather than to write one, you're on a Chromebook or a tablet, your laptop is locked down, or your environment setup went sideways and you'd rather learn something than debug a package manager.

## What you need

- A current Chrome, Edge, or Safari. The playground uses the Web Audio API, which older browsers don't have.
- **Headphones.** Your laptop speakers will feed the agent's own voice back into the microphone, and Lab 2 is where that gets confusing.
- A free Deepgram account. The playground gates the agent behind sign-in — you'll see *"Log in or sign up to talk to the agent"* until you do. Signing up takes a minute at [console.deepgram.com/signup](https://console.deepgram.com/signup) and comes with free credit; no card.
- No microphone? Skip ahead to [Talking without a microphone](#talking-without-a-microphone). Everything still works.

## What you're actually building

A voice agent is three models in a row, wired together over a single connection:

```
your voice ──▶ Speech to Text ──▶ LLM ──▶ Text to Speech ──▶ the agent's voice
                  (Flux)         (thinks)      (speaks)
```

Deepgram runs all three and manages the connection between them. Your job — in code or in this playground — is configuration: which models, what the agent is told to do, and which of your functions it's allowed to call.

The one idea worth carrying out of this room: **the playground's settings panel is a form over a JSON document.** Every control you touch writes one field of a `Settings` message the playground sends the moment a conversation opens. The developers next to you are typing that same document by hand. Here it is, trimmed to the fields you'll change today:

```json
{
  "agent": {
    "listen":  { "provider": { "type": "deepgram", "model": "flux-general-en" } },
    "think":   { "provider": { "type": "open_ai", "model": "gpt-4o-mini", "temperature": 0.7 },
                 "prompt": "You are a helpful AI assistant...",
                 "functions": [ ]  },
    "speak":   { "provider": { "type": "deepgram", "model": "aura-2-thalia-en" } },
    "greeting": "Hello! What would you like to talk about?"
  }
}
```

**Transcription model** is `listen`. **LLM** and **Agent prompt** are `think`. **Voice** is `speak`. Once you see the panel as a view of that document, the code track stops looking like a different activity.

## Following along with the room

| Workshop step | Easy Mode equivalent |
|---|---|
| 1 — Setup | [Lab 1 — Get in and say hello](#lab-1--get-in-and-say-hello) |
| 2 — Connect | Lab 1 (the playground opens the connection for you) |
| 3 — Hear the agent | Lab 1 |
| 4 — Talk to the agent | Lab 1 |
| 5 — Barge-in | [Lab 2 — Interrupt it](#lab-2--interrupt-it) |
| 6 — Make it yours | [Lab 4 — Make it yours](#lab-4--make-it-yours) |
| 7 — Function calling | [Lab 5 — Let it call a function](#lab-5--let-it-call-a-function) |
| 8 — Optimization | [Lab 3 — Tune turn detection](#lab-3--tune-turn-detection) — Easy Mode reaches it earlier |
| Finished | [Lab 6 — Take the config with you](#lab-6--take-the-config-with-you) |

You'll finish each lab faster than the code track finishes its step. Spend the spare minutes on the **Going further** prompts — they're where the interesting arguments happen.

## Lab 1 — Get in and say hello

**Goal:** A real conversation with an agent, in about three minutes.

1. Open [playground.deepgram.com/voice-agent](https://playground.deepgram.com/voice-agent) and log in.
2. Under **Try a use case:** pick **General**. The other presets — Healthcare, Customer support, Sales, Financial services — load a prompt and settings tuned for that scenario, and you'll come back to them in Lab 4.
3. Click **Talk To Your Agent**. The browser asks for microphone permission; allow it.
4. Talk. Ask it what it does, then interrupt yourself, then trail off mid-sentence and see what it does with the silence.
5. Click **End Conversation** when you're done.

Watch the message list while you talk. Every turn appears there, and **Expand all** opens the raw events underneath — this is the same stream of messages the Python code is reacting to. Turn on **Show client audio** to see your own audio going out alongside the agent's coming back.

**One thing that will trip you up:** while a conversation is open, the playground locks the settings. The playground tells you so — *"While the connection is open, you cannot update the agent in the Playground."* Click **End Conversation**, change your setting, then start again. That's a playground rule, not an API rule; over the API you can update a live agent mid-conversation.

> **Check yourself** — Three models run behind that conversation. Which one decided *when you were finished speaking*?

### Talking without a microphone

Under the message list, the **Talk for me** box takes typed input and sends it to the agent as if you'd said it — click **Send text** or press Ctrl+Enter. The agent still replies out loud. Use this on a tablet with no mic access, in a room too loud to talk in, or any time you want to send the exact same sentence twice to compare two configurations.

## Lab 2 — Interrupt it

**Goal:** Feel the difference between a demo and something people will actually use.

Ask the agent a question with a long answer — *"explain how a car engine works"* — and then talk over it about two seconds in.

It stops. That's **barge-in**, and it's the single feature that makes a voice agent feel like a conversation instead of a phone tree. The moment Deepgram hears speech that looks like a real turn, it stops generating audio and starts listening.

You get it for free here. The code track spends a whole step on it, because in code you have to throw away the audio you already have queued up locally — the agent stops talking, but your speaker keeps playing the last two seconds you handed it. Ask a neighbor on the code track to show you their step 5 before and after.

**Now break it:** take your headphones off and let the agent talk into your own microphone. It interrupts itself, because it can't tell its voice from yours. This is why the room is full of headphones.

> **Check yourself** — Why does interrupting need work on the client at all, if Deepgram already stopped sending audio?

## Lab 3 — Tune turn detection

**Goal:** See the trade-off between a snappy agent and one that lets you finish a sentence.

The agent's sense of "you're done talking" comes from Flux, Deepgram's conversational speech-to-text model. Turn detection lives inside the model rather than in a timer on the client, and it's tunable. The Voice Agent panel doesn't expose those dials, so take a short side trip to see them directly:

1. Open the **Streaming Speech to Text** playground and choose the turn-based streaming mode with the `flux-general-en` model.
2. Click **Start listening** and talk. Watch the events: `StartOfTurn`, `EagerEndOfTurn`, `TurnResumed`, `EndOfTurn`, each with a confidence score.
3. Find these three settings and move them:

| Setting | What it does | Default |
|---|---|---|
| **End of Turn Threshold** | How confident the model must be that you've finished before it fires `EndOfTurn`. Lower (0.5) answers faster and risks cutting you off; higher (0.9) waits for certainty. | 0.7 |
| **End of Turn Timeout** | Ends the turn after this much silence regardless of confidence. | 5000 ms |
| **Eager End of Turn Threshold** | A lower bar that fires an early "probably done" signal, so an agent can start drafting a reply speculatively. Must be at or below the End of Turn Threshold. | — |

Try 0.5, then 0.9, saying the same halting sentence both times: *"I'd like to order a… uh… large coffee."* At 0.5 the model calls the turn during your "uh." At 0.9 it waits you out, and the reply arrives noticeably later.

No value is correct in the abstract. A drive-through agent wants speed; an agent taking a credit card number over the phone wants patience. You're choosing which mistake to make.

> **⏸ Pause — check in with the instructor**
> Good moment to compare notes with the code track, who are measuring the same trade-off in milliseconds.

## Lab 4 — Make it yours

**Goal:** Give the agent a job, a personality, and a voice. This is the lab with the least to click and the most to play with.

End the conversation first, then open the settings panel. Four fields matter:

**Agent prompt** — the standing instructions the model sees with every turn. Personality, job, boundaries.

**Greeting (Optional)** — the first thing the agent says. Leave it blank and the agent waits for the user to speak first, which is the right choice more often than people expect.

**Voice** (under the **Voice** section) — purely how it sounds. It changes nothing about what the agent says.

**LLM** and **LLM Temperature (Optional)** — the brain, and how much it varies. Low temperature for an agent that must say the same thing every time; higher for a chatty one.

### Writing a prompt for speech

Writing prompts for a voice agent differs from writing them for a chatbot in two specific ways, and both of them bite immediately.

**Tell it that it's speaking.** LLMs default to writing. Without an explicit instruction you get markdown, and text-to-speech reads it literally — `**important**` comes out as "star star important star star."

**Tell it to be brief.** A four-sentence answer that scans fine in a chat window feels interminable when you have to sit through it. Voice punishes verbosity in a way text doesn't.

Keep it short for a third reason: every token goes to the model on every turn, so a long prompt slows down the first reply.

Paste this into **Agent prompt** as a starting point, then make it your own:

```
You are Sam, a barista at a small coffee shop. Your job is to take a
drink order: the drink, the size, and the name for the cup.

You are speaking out loud. Never use markdown, bullet points, lists,
or emoji. Keep every reply to one or two sentences.

Ask for one thing at a time. When you have all three, read the order
back and confirm it. If someone asks about anything other than coffee,
say you only work the espresso bar and steer them back to the order.
```

And into **Greeting (Optional)**:

```
Morning! What can I get started for you?
```

Start the conversation and order something. Then push at it: ask Sam for the weather, ask it to write you a Python script, ask what it thinks about a movie. A prompt that holds under pressure is the difference between a demo and a product.

**Then change one thing at a time.** Swap the voice and run the same order — same words, different job applicant. Raise the temperature to 1.2 and watch it get chatty and start improvising drinks. Load the **Healthcare** or **Customer support** preset and read its prompt closely; professionals wrote those, and they're worth stealing structure from.

> **Check yourself** — Name the two prompt instructions that matter for speech but not for chat.

**Going further:** give the agent a constraint it must hold — "you never quote a price" — and spend two minutes trying to talk it out of the constraint. Prompt injection against a voice agent is the same problem as against a chat agent, except your attacker is talking out loud.

## Lab 5 — Let it call a function

**Goal:** Understand how an agent reaches outside its own head.

Ask your agent what time it is. It will make something up with total confidence, because a language model has no clock. Function calling closes that gap and every gap like it: your database, your API, the user's order history, today's date.

The flow has four hops:

1. The configuration advertises a function — a **name**, a **description**, and a schema for its arguments.
2. The model decides a turn warrants calling it, and Deepgram emits a **function call request** with the arguments it chose.
3. Something runs the function and returns a result.
4. The model works that result into its reply, and the agent speaks it.

### See it happen

Open the **Functions** section of the settings panel. Two example functions ship with the playground:

- **Arithmetic (Example)** — `do_arithmetic`, which takes an `operation` (add, subtract, multiply, divide) and a list of `numbers`.
- **End Conversation (Example)** — `end_conversation`, which the agent calls when it hears a phrase that means the conversation is over.

Toggle **Arithmetic (Example)** on, then expand it. You get the **Function name** and the **Function JSON** — the exact schema the model reads. Read the `description` fields carefully; you're about to see why they matter.

Start a conversation and ask something arithmetic: *"what's four hundred and seventeen times nineteen?"* Watch the message list. You'll see the function call request with the arguments the model picked, then the response, then the agent speaking the answer. Expand those events and compare the arguments to the schema you just read.

Then toggle **End Conversation (Example)** on, start again, and say goodbye. Different function, same four hops.

### The two things worth remembering

**The description is a prompt.** It is the only thing the model reads when deciding whether to call your function. Write it to say *when* to use the function, not just what it does. "Get the current time" is a weak description; "Get the current date and time in a given IANA timezone. Use this whenever the user asks what time it is or what today's date is" is one the model can act on. Nine times out of ten, a function that never fires has a description problem, not a wiring problem.

**Where the function runs is one field.** In the JSON, a function definition can carry an `endpoint`:

```json
{
  "name": "get_order_status",
  "description": "Look up the status of a customer order by order number. Use this whenever the caller asks where their order is.",
  "parameters": {
    "type": "object",
    "properties": {
      "order_number": { "type": "string", "description": "The order number the caller reads out." }
    },
    "required": ["order_number"]
  },
  "endpoint": { "url": "https://api.example.com/orders", "method": "post" }
}
```

With `endpoint` set, Deepgram calls that URL itself — server-side, no application of yours involved. Leave `endpoint` out and Deepgram sends the call down the connection to your app and waits for you to answer, which is what you want when the function touches local state or credentials you'd rather not put on a public URL. That single omitted field is the whole distinction, and the code track's step 7 turns on it.

The playground's Functions section ships those two examples rather than an editor, so writing your own is where Easy Mode hands off. You now know exactly what to write, and the [function calling documentation](https://developers.deepgram.com/docs/voice-agents-function-calling) has the rest.

> **⏸ Pause — check in with the instructor**
> Sketch a function for your own use case: what would your agent need to look up that a model cannot possibly know? Share one with the room. This is the most useful two minutes in the workshop.

## Lab 6 — Take the config with you

You've built something. Don't leave it in a browser tab.

- The **Code Sample** tab turns your current settings into working code you can hand to a developer, or open yourself later.
- **Use this config and get started** and the `config.json` download give you the raw settings document — the same JSON from the top of this page, now filled in with your choices.
- You'll need an API key to run any of it. **Get an API key** → **Create Key** in the playground, or grab one from [console.deepgram.com](https://console.deepgram.com/). Copy the secret when the playground shows it; you can't see it again.

Hand that config to someone on the code track and ask them to drop it into `steps/99-final/main.py`. Watching your barista come out of somebody else's terminal is a good way to end the session.

## When something goes wrong

**"Log in or sign up to talk to the agent"** — The agent needs an account. Free to create, no card.

**The settings are grayed out** — A conversation is open. Click **End Conversation** first.

**It interrupts itself constantly** — Speakers, not headphones. It's hearing its own voice.

**No microphone prompt appeared** — Check the site permissions in your browser's address bar; a previous "block" sticks. Failing that, use **Talk for me** and **Send text**.

**"Your free agent trial minutes have been exhausted"** — Add credit to the account, or share a machine with a neighbor for the rest of the session.

**It cuts you off mid-sentence** — Working as designed, and Lab 3 is about exactly that trade-off.

**It reads punctuation out loud** — Your prompt hasn't told it that it's speaking. Back to Lab 4.

## Where to go next

You configured a voice agent, tuned how patiently it listens, gave it a job and a voice, and watched it call a function. That's the whole workshop; the code track types more and learns the same things.

If you want to run one yourself, the main [README](README.md) starts from an empty folder, and every step is a complete working program. Nothing you learned here goes to waste — the labs above map one to one onto the steps, and the settings panel you just used is the JSON those steps build.

- [Voice Agent documentation](https://developers.deepgram.com/docs/voice-agent)
- [Prompting voice agents](https://developers.deepgram.com/docs/prompting-voice-agents)
- [Function calling](https://developers.deepgram.com/docs/voice-agents-function-calling)
- [Flux and turn detection](https://developers.deepgram.com/docs/flux)
- [Discord](https://discord.gg/xWRaCDBtW4) and [GitHub Discussions](https://github.com/orgs/deepgram/discussions)
