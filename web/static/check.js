// Step 1's browser-side setup check.
//
// Deliberately uses the same calls the workshop uses -- an AudioContext pinned
// to the agent's rate, an AudioWorklet, getUserMedia with echo cancellation --
// so that passing here means the real thing will work, rather than merely
// suggesting it.

const RECORD_SECONDS = 4;
const TONE_HZ = 440;
const TONE_SECONDS = 1;
// Deliberately low: quiet built-in microphones are normal and still work fine.
const GOOD_PEAK = 0.02;
const AGENT_RATE = 24000;

const ui = {
  run: document.getElementById("run"),
  status: document.getElementById("status"),
  level: document.getElementById("level-bar"),
  banner: document.getElementById("banner"),
  verdict: document.getElementById("verdict"),
};

const results = {};

/**
 * Record one check's outcome and paint its row.
 *
 * @param {string} name Which row, matching its data-check attribute.
 * @param {string} state One of "pass", "warn", "fail".
 * @param {string} detail Short explanation shown beside the row.
 */
function report(name, state, detail) {
  results[name] = state;
  const row = document.querySelector(`[data-check="${name}"]`);
  row.dataset.state = state;
  row.querySelector(".mark").textContent = { pass: "OK", warn: "!?", fail: "XX" }[state];
  row.querySelector(".detail").textContent = detail;
}

/**
 * Set the status pill.
 *
 * @param {string} text Label to show.
 * @param {string} tone One of "idle", "busy", "live", "error".
 */
function setStatus(text, tone) {
  ui.status.textContent = text;
  ui.status.dataset.tone = tone;
}

/**
 * Show a message above the verdict.
 *
 * @param {string} text Message body. Empty hides it.
 * @param {string} tone Either "error" or "info".
 */
function setBanner(text, tone = "error") {
  ui.banner.textContent = text;
  ui.banner.dataset.tone = tone;
  ui.banner.hidden = !text;
}

/**
 * Wait.
 *
 * @param {number} ms How long, in milliseconds.
 * @returns {Promise<void>} Resolves after the delay.
 */
function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Run the two checks that need no permission, plus the key check.
 */
async function runPassiveChecks() {
  if (window.isSecureContext) {
    report("secure", "pass", `${location.origin} is a secure context`);
  } else {
    report(
      "secure",
      "fail",
      "Microphone access is blocked here. Open this page on http://127.0.0.1 rather than a LAN address.",
    );
  }

  const hasWorklet = Boolean(window.AudioWorklet);
  const hasMedia = Boolean(navigator.mediaDevices?.getUserMedia);
  if (hasWorklet && hasMedia) {
    report("support", "pass", "AudioWorklet and getUserMedia are available");
  } else {
    report("support", "fail", "This browser is too old. Use a current Chrome, Firefox, or Safari.");
  }

  try {
    const status = await (await fetch("/api/check")).json();
    report("key", status.key_ok ? "pass" : "fail", status.key_detail);
  } catch (error) {
    report("key", "fail", `Could not reach the Python check: ${error}`);
  }
}

/**
 * Open the microphone, watch the level for a few seconds, then play a tone.
 */
async function runAudioChecks() {
  ui.run.disabled = true;
  ui.status.hidden = false;
  setBanner("");

  let context = null;
  let stream = null;

  try {
    setStatus("opening the microphone", "busy");
    stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
        channelCount: 1,
      },
      video: false,
    });

    context = new AudioContext({ sampleRate: AGENT_RATE });
    await context.resume();

    // Worth reporting rather than assuming: iOS Safari ignores the requested
    // rate, and the worklets resample instead. Everything still works, just
    // through an extra step.
    const rateNote =
      Math.round(context.sampleRate) === AGENT_RATE
        ? ""
        : ` Browser gave ${Math.round(context.sampleRate)} Hz instead of ${AGENT_RATE} Hz; audio will be resampled.`;

    // getSettings() reports what the browser actually granted, which is not
    // always what was asked for. Echo cancellation is what lets this workshop
    // run without headphones, so it is worth knowing when it is missing.
    const settings = stream.getAudioTracks()[0]?.getSettings() ?? {};
    const aecNote = settings.echoCancellation === false ? " Echo cancellation is off -- wear headphones." : "";

    await context.audioWorklet.addModule("/worklets.js");
    const capture = new AudioWorkletNode(context, "capture-processor", {
      processorOptions: { targetRate: AGENT_RATE, chunkFrames: 1920 },
    });

    let peak = 0;
    capture.port.onmessage = (event) => {
      if (event.data.type === "level") {
        peak = Math.max(peak, event.data.value);
        ui.level.style.width = `${Math.min(100, event.data.value * 250)}%`;
      }
    };

    const silence = context.createGain();
    silence.gain.value = 0;
    context.createMediaStreamSource(stream).connect(capture).connect(silence).connect(context.destination);

    setStatus(`say something -- listening for ${RECORD_SECONDS}s`, "live");
    await sleep(RECORD_SECONDS * 1000);
    ui.level.style.width = "0%";

    if (peak >= GOOD_PEAK) {
      report("mic", "pass", `Heard you (peak ${peak.toFixed(2)}).${rateNote}${aecNote}`);
    } else {
      report(
        "mic",
        "warn",
        `Opened, but heard almost nothing (peak ${peak.toFixed(3)}). Check you are not muted and the right input is selected.${aecNote}`,
      );
    }

    setStatus(`playing a ${TONE_HZ} Hz tone`, "busy");
    const tone = context.createOscillator();
    const gain = context.createGain();
    tone.frequency.value = TONE_HZ;
    // Quarter amplitude -- loud enough to hear, quiet enough in headphones.
    gain.gain.value = 0.25;
    // Fade the tail so it does not end on a click.
    gain.gain.setValueAtTime(0.25, context.currentTime + TONE_SECONDS * 0.9);
    gain.gain.linearRampToValueAtTime(0, context.currentTime + TONE_SECONDS);
    tone.connect(gain).connect(context.destination);
    tone.start();
    tone.stop(context.currentTime + TONE_SECONDS);
    await sleep(TONE_SECONDS * 1000 + 200);

    report("speaker", "pass", "Played a tone -- you should have heard it");
    // The pill reads as a second button sitting next to the real one, so retire
    // it once there is no more progress to report and say "Done" in the callout.
    // The audio half can finish clean while a passive check or the mic level
    // still needs attention, so only claim a pass when every row agrees.
    ui.status.hidden = true;
    const states = Object.values(results);
    if (states.includes("fail") || states.includes("warn")) {
      setBanner("Done. Some checks need attention -- see below.", "info");
    } else {
      setBanner("Done, all checks pass. Continue to the next step.", "pass");
    }
  } catch (error) {
    if (error?.name === "NotAllowedError") {
      report("mic", "fail", "Permission denied. Allow the microphone in the address bar, then run this again.");
    } else if (error?.name === "NotFoundError") {
      report("mic", "fail", "No microphone found. Plug one in or pick one in your system settings.");
    } else {
      report("mic", "fail", String(error?.message ?? error));
    }
    setStatus("failed", "error");
  } finally {
    stream?.getTracks().forEach((track) => track.stop());
    await context?.close().catch(() => {});
    ui.run.disabled = false;
    verdict();
  }
}

/**
 * Summarise the run at the bottom of the page.
 */
function verdict() {
  const states = Object.values(results);
  if (states.length < 5) {
    return;
  }
  if (states.includes("fail")) {
    ui.verdict.textContent =
      "Some checks did not pass. If you are in a workshop, this is the moment to raise your hand.";
    ui.verdict.dataset.tone = "error";
  } else if (states.includes("warn")) {
    ui.verdict.textContent = "Good enough to continue, but read the warnings above first.";
    ui.verdict.dataset.tone = "warn";
  } else {
    ui.verdict.textContent = "All checks passed. Stop the server with Ctrl+C and move on to Step 2.";
    ui.verdict.dataset.tone = "pass";
  }
}

ui.run.addEventListener("click", () => void runAudioChecks());

void runPassiveChecks();
setStatus("not started", "idle");
