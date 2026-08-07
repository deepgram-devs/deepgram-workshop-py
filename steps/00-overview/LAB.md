# Step 0 — Overview

**Goal:** Understand the parts of a voice agent before you write a line of it.

**You'll learn**

- The three models every voice agent needs, and what each one does
- What the Voice Agent API orchestrates so you don't have to
- Why Flux changes where turn-taking happens — and what that removes from your code

No code in this step. Read it, then run Step 1.

## A voice agent is three models in a loop

Audio comes in, audio goes out, and a model in the middle decides what to say. Each job belongs to a different kind of model.

**Speech-to-text (STT)** turns microphone audio into words. This workshop uses **Flux**, Deepgram's conversational speech-to-text model. Flux streams transcripts as you speak, so nothing waits for a complete utterance.

**A large language model (LLM)** is the brain. It takes the transcript, mixes it with the conversation history and the agent's standing instructions, and decides what to say back. We use OpenAI's `gpt-4o-mini` because it's fast and cheap, and speed matters more than raw capability when somebody is waiting to hear a reply. The same pattern works with Anthropic, Google, Groq, and AWS Bedrock — you swap a provider class, not your architecture.

**Text-to-speech (TTS)** turns the reply back into audio. We use **Flux TTS**, Deepgram's streaming voice engine built for conversation.

> **Check yourself** — What are the three building blocks of a voice agent, and which one holds the conversation history?

## The Voice Agent API does the orchestration

You could wire those three together yourself: call your own STT, pipe the transcript into your own LLM call, feed the response into your own TTS. You'd spend most of your time on plumbing and latency, and very little on what the agent actually does.

The Voice Agent API collapses all three into one WebSocket. You describe what you want:

- Which STT model
- Which LLM provider and model
- Which TTS voice
- The agent's personality and greeting

…and you get a socket. Audio bytes go in, audio bytes come out. Deepgram runs the pipeline server-side and manages the handoffs between providers.

Over the next eight steps you *configure that orchestrator* and react to what it sends you. You will never reimplement it.

> **Check yourself** — Name two things the Voice Agent API handles that you'd otherwise write yourself.

## What Flux changes

This is the part worth slowing down for, because it's where voice agents differ most from what you'd expect.

In a traditional pipeline, your client decides when the user has stopped talking. You measure audio energy, you set a silence threshold, you write voice activity detection, and you get it slightly wrong forever. Turn-taking lives in your code.

Flux performs turn detection **inside the model**. It scores every turn for end-of-turn confidence as the audio streams in, and tells you what it concluded. You will not write a silence threshold anywhere in this workshop.

That removes a great deal of code and leaves you with exactly one obligation: when Flux says the user started talking, **stop your speaker immediately**. The agent stops sending audio the moment it knows — but whatever it already sent is sitting in your playback buffer, and it will keep talking over the user until you clear it.

That single responsibility gets its own step ([Step 5](../05-barge-in/LAB.md)), because it's the difference between a demo and something a person would willingly talk to.

> **Check yourself** — Where does turn detection happen with Flux, and what is the client still responsible for?

## What you'll have built

By the end of Step 8, roughly 350 lines that:

- Open a WebSocket and negotiate an agent configuration
- Stream microphone audio from a browser without blocking the thread that plays the reply
- Play the agent's speech as it arrives
- Cut playback the instant you interrupt
- Call your Python and speak the result
- Let you tune how patient the agent is, and measure what it costs

## How the workshop is laid out

Every step is a **complete, working program**. `steps/03-hear-the-agent/main.py` already does everything Steps 1 and 2 built — you open it, run it, and add the piece that step is about.

That means two useful things. If you fall behind, skip ahead and keep going. And when you're stuck, the *next* folder is the answer key: `steps/04-talk-to-the-agent/main.py` is Step 3, finished.

Work the `TODO (Step N.x)` blocks in `main.py`, in order. `LAB.md` explains why each one matters.

> **Check yourself** — You're stuck halfway through Step 5. Where do you look for the working version?

---

With the mental model in place, get your machine ready and confirm it can move audio.

**Next:** [Step 1 — Setup](../01-setup/LAB.md)
