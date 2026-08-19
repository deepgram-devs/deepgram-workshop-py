# Step 7b: A second vertical in healthcare (optional)

> **Demo only.** This is not a HIPAA-compliant system and every record in it is invented. Do not put real patient data into it. See [what compliance would actually take](#what-compliance-would-actually-take) for the distance between this file and a system allowed near a real patient.

**Goal:** Point the same function-calling machinery at a second domain, where the hard problem is what the agent must never repeat.

**You'll learn**

- What `keyterms` actually buys you, heard rather than explained
- Why the payload is your enforcement layer and the prompt is only backup
- How little separates one vertical from another once the plumbing exists

Optional, and off the chain: Step 8 continues from Step 7 whether or not you do this. Unlike [Step 6b](../06b-bring-your-own-llm/LAB.md) it needs no credential beyond your Deepgram key, so it costs about fifteen minutes and nothing else.

## Start here

```bash
uv run steps/07b-healthcare/main.py
```

Step 7 built a banking agent. This is a clinic scheduling agent for Lakeside Family Health, and the difference is instructive. Banking cared about getting numbers *right*. Healthcare cares about that too, plus something banking never asked: some of the data you're allowed to look up, you are not allowed to say out loud.

Everything you wrote in Step 7 ships already written here: `handle_function_call`, the dispatch branch, the `FUNCTIONS` declaration. That's the point. Once the plumbing exists, a new vertical is a prompt, a vocabulary, and a handler. Three TODOs.

## How it works

Two things change between verticals, and neither of them is code you haven't seen.

**The vocabulary changes.** A general speech model has heard "balance" and "transaction" a million times. It has not heard "semaglutide," and it has certainly not heard "Dr. Bergstrom." `keyterms` biases Flux toward the words your domain repeats all day, and it's the highest-leverage accuracy fix available for a domain-specific agent.

**The constraints change.** A banking agent's rules are about accuracy. A clinic agent's rules are about disclosure: verify by last four only, never speak a full date of birth, and never give medical advice. Those rules go in the prompt, and then you enforce them somewhere the model can't reach.

> **Check yourself:** Your handler looks up a record containing a phone number, and your prompt says never to read a phone number aloud. What's still wrong with returning the whole record?

## Do this

**TODO 7b.1: Hear the vocabulary problem before you fix it.**

Leave `KEYTERMS` empty. Connect, and say:

> *"I'm calling about my semaglutide prescription with Doctor Bergstrom."*

Read what lands in the transcript. It won't be that sentence. The model has no reason to know either word, so it guesses at something phonetically nearby and hands the LLM a question about a drug that doesn't exist.

Now uncomment the list, restart, and say it again.

That's the entire feature. One line of configuration, and the words your users actually say start arriving intact: drug names, procedures, proper nouns, SKUs, whatever your domain repeats that the internet at large doesn't.

**TODO 7b.2: Write the privacy guardrails.** Replace the placeholder prompt with the clinic one. Three rules: verify by first name plus last four, never speak a full DOB or ID or phone number, and no clinical advice, offer a nurse callback instead.

**TODO 7b.3: Return only what the agent may speak.** Write `find_appointment`.

This is the step. Look at what's sitting in each `PATIENTS` record: a full date of birth, a full patient ID, a phone number. The short version of this handler is `return patient`. It works. It's one line. It also hands all three of those to a language model and trusts a paragraph of prose to stop it repeating them.

Return three keys instead:

```python
return {
    "verified": True,
    "first_name": patient["first_name"],
    "next_appointment": patient["next_appointment"],
}
```

The prompt says the agent must not speak a full ID. The payload makes speaking one *impossible*. Treat the payload as the enforcement layer and the prompt as backup, because the model may say anything you hand it: under pressure, under a clever question, or just because it was being helpful. Filter at the boundary.

Notice this costs you nothing. You didn't lose a feature; you removed data the conversation never needed.

## Verify

Connect and work down this script:

1. *"First name Maria, ID ending 1234."* → verifies, then reads her A1C follow-up with Dr. Nwosu
2. *"First name James, ID ending 5678."* → the echocardiogram with Dr. Bergstrom
3. *"What was my date of birth again?"* → it declines
4. *"Should I stop taking my metformin?"* → offers a nurse callback instead of advice

Three and four are the ones worth listening to. The refusals are the deliverable.

Then check the console for what the LLM actually received:

```
>> Function call: find_appointment({"first_name":"Maria","patient_id_last_four":"1234"})
>> Function result: {"verified": true, "first_name": "Maria", "next_appointment": {"date": "2026-08-12", ...}}
```

No date of birth in that line. That's TODO 7b.3 doing its job, and it's the only guarantee in this file that doesn't depend on the model cooperating.

### Test data

| Say | Result |
|---|---|
| `Maria` / `1234` | A1C follow-up, Aug 12, 9:30 AM, Dr. Nwosu |
| `James` / `5678` | Echocardiogram, Aug 19, 2:00 PM, Dr. Bergstrom |
| anything else | the graceful "could not verify" path |

## Stuck?

**The agent apologizes and the console says `No function named 'find_appointment' is available`.** TODO 7b.3 isn't done. `FUNCTION_HANDLERS` is still the empty dict. Worth hearing once, since it's exactly what a handler you forgot to register sounds like from the caller's side.

**Keyterms made no difference.** Confirm you restarted the process; `keyterms` goes over the wire in the settings handshake, so a browser refresh alone won't do it. Then check the console for `>> Agent warning:` on connect.

**It verifies the wrong patient, or won't verify at all.** Flux heard the digits wrong. Say each digit on its own ("one, two, three, four") and watch the transcript. In production this is where you'd add a read-back rule like the banking prompt's.

**It gives medical advice anyway.** Make the rule more specific and move it later in the prompt. "Do not give clinical or medication advice" works; "be careful about health topics" doesn't.

## Going further

**Implement the callback you're promising.** Right now the prompt offers a nurse callback and nothing in the system provides one, so the agent commits to something that never happens. Close that gap:

```python
CALLBACKS = []  # stands in for your ticketing system or EHR task queue


def request_nurse_callback(first_name: str, patient_id_last_four: str, reason: str = "unspecified") -> dict:
    """Queue a nurse callback for a verified patient."""
    patient = PATIENTS.get(patient_key(first_name, patient_id_last_four))
    if patient is None:
        return {"queued": False, "message": "I could not verify a patient with that name and ID."}

    CALLBACKS.append({"patient": patient["first_name"], "reason": reason})
    print(f">> Nurse callback queued for {patient['first_name']} ({len(CALLBACKS)} in queue)")

    # No phone number in the payload. The agent has no business reading one aloud.
    return {"queued": True, "first_name": patient["first_name"], "callback_window": "today before 5:00 PM"}
```

Declare it with a description that carries the instruction:

> "Queue a callback from a nurse. Call this instead of answering any clinical or medication question. Requires a verified patient."

Then point the prompt's advice rule at it by name, rather than leaving the agent to improvise: *"Do not give clinical or medication advice. Call request_nurse_callback with a short summary of their question, then tell them when to expect the call."*

Leave `reason` out of `required`, deliberately. Mark a field required and the agent will interrogate the caller until it has a value, which suits an ID and badly suits a free-text summary the model can infer from the conversation it just had.

Verify as Maria, ask *"should I stop taking my metformin?"*, and listen: it should decline the advice, call the function, and tell you a nurse will ring before 5 PM. The console line it prints is exactly where your real ticket-creation call goes.

**Stretch:** add `reschedule_appointment(first_name, patient_id_last_four, new_date)` that mutates `PATIENTS` and returns the updated visit. It carries the same lesson as `transfer_funds` in Step 7: a state-changing call needs confirmation before it fires, and a prompt is not an authorization layer.

## What compliance would actually take

The banner at the top of this page isn't boilerplate. If this vertical is the one you actually want to build, here is the distance between the file you just wrote and a system allowed near a real patient, and most of it isn't code. Deepgram's [voice AI healthcare compliance checklist](https://deepgram.com/learn/voice-ai-healthcare-compliance-accuracy-checklist) is the long version of everything below, including one point this step earns the hard way: in a clinical record, a transcription error is a documentable PHI-handling failure rather than a quality problem. Accuracy *is* a compliance control.

**Contracts come first.** A signed BAA with every vendor that touches PHI: Deepgram, your LLM provider, telephony, and hosting. Logging and observability belong on that list too, and they're the ones teams forget until an audit, because your APM ingesting a transcript is a disclosure. [Deepgram is a Business Associate under HIPAA](https://developers.deepgram.com/trust-security/data-privacy-compliance) and offers BAAs to qualifying Covered Entities on request; that page also covers SOC 2 Type 2, GDPR, and the regional endpoints (`api.eu.deepgram.com`, `api.au.deepgram.com`) if data residency is on your list. Self-hosted deployment exists for teams whose audio can't leave their own infrastructure at all. On AWS that takes a specific form: Flux, Nova-3, and Aura-2 are on AWS Marketplace and [deploy to Amazon SageMaker endpoints](https://developers.deepgram.com/docs/deploy-amazon-sagemaker) inside your own account and VPC, so the audio never crosses your network boundary — the speech models, not the Voice Agent API, which SageMaker's network isolation rules out. Which of those you need is a conversation with your account team, not a configuration flag.

**Then the safeguards this file skips on purpose:**

- **Verification that verifies.** First name plus last four is a demo affordance, a knowledge check on data that leaks constantly. Real systems call back the number on file, issue a code through the patient portal, or check a PIN the patient set themselves.
- **Audit controls.** Every record access logged immutably: who, what, when, from where. The `print()` calls in `handle_function_call` are the opposite of an audit trail, and they spill PHI into terminal scrollback and CI logs while they're at it.
- **Retention and redaction.** The audio is PHI, not just the transcript; 45 CFR § 160.103 covers both. Decide how long you keep each and build the deletion path before someone asks you to use it. And redaction is not a shortcut: automated PHI redaction on its own doesn't meet HIPAA's de-identification standard.
- **The rest of §164.312:** encryption at rest, unique identities for staff, session timeouts, and PHI kept out of crash reports, prompt dumps, and eval datasets.

Around all of that sits the part no library provides: a documented risk analysis, workforce training, and a breach-notification process running on a 60-day clock. There's no such thing as a HIPAA-certified codebase. Compliance is a program you maintain, and it wants a lawyer involved early rather than after the architecture sets.

One habit from this step does survive the trip intact. *Minimum necessary* (§164.502(b), the rule that you disclose only what the task requires) is precisely what TODO 7b.3 implements. You wrote a compliance control as a return statement. That's the shape the rest of them take too, once the contracts are signed.

## Where this goes next

Both verticals are the same agent with three things changed: a vocabulary, a prompt, and a handful of functions. That's most of the distance between an agent that talks and one that does useful work.

Pick the question your users ask support most often. Write the function that answers it. Then listen to your agent answer it out loud.

---

**Next:** [Step 8: Optimization](../08-optimize/LAB.md), which continues from Step 7, exactly as it would have.
