// Wires a browser tab to the Python step running behind it.
//
// This file owns no agent logic at all. It opens a microphone, plays what
// arrives, and forwards control messages to the DOM. Everything about what the
// agent says, when it speaks, and what it can do lives in steps/NN/main.py.

const ui = {
  connect: document.getElementById("connect"),
  status: document.getElementById("status"),
  level: document.getElementById("level-bar"),
  transcript: document.getElementById("transcript"),
  activity: document.getElementById("activity"),
  banner: document.getElementById("banner"),
};

const session = {
  context: null,
  stream: null,
  // Kept in a long-lived object on purpose: Chrome and Safari will collect a
  // MediaStreamAudioSourceNode that only lives in a local variable, and the
  // microphone goes silent with nothing in the console to explain it.
  source: null,
  capture: null,
  playback: null,
  socket: null,
  connected: false,
};

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
 * Show a dismissable message above the transcript.
 *
 * @param {string} text Message body. Empty hides the banner.
 * @param {string} tone Either "error" or "info".
 */
function setBanner(text, tone = "error") {
  ui.banner.textContent = text;
  ui.banner.dataset.tone = tone;
  ui.banner.hidden = !text;
}

/**
 * Append one line to the transcript and scroll to it.
 *
 * @param {string} role Who said it.
 * @param {string} content What they said.
 */
function addTranscript(role, content) {
  const line = document.createElement("div");
  line.className = "line";
  line.dataset.role = role;

  const who = document.createElement("span");
  who.className = "who";
  who.textContent = role;

  const what = document.createElement("span");
  what.className = "what";
  what.textContent = content;

  line.append(who, what);
  ui.transcript.append(line);
  ui.transcript.scrollTop = ui.transcript.scrollHeight;
}

/**
 * Check the two browser capabilities this page cannot work without.
 *
 * Both fail the same silent way on an insecure origin, which is why the address
 * bar is worth naming in the message.
 *
 * @returns {boolean} Whether it is worth enabling the connect button.
 */
function checkSupport() {
  if (!window.isSecureContext) {
    setBanner(
      "This page must be served from localhost or over HTTPS. Microphone access " +
        "is disabled on other addresses. Try http://127.0.0.1:8000/ instead.",
    );
    return false;
  }
  if (!window.AudioWorklet || !navigator.mediaDevices?.getUserMedia) {
    setBanner("This browser has no AudioWorklet or microphone support. Try a current Chrome, Firefox, or Safari.");
    return false;
  }
  return true;
}

/**
 * Build the audio graph, open the microphone, and connect to the step.
 */
async function connect() {
  ui.connect.disabled = true;
  setBanner("");
  setStatus("starting audio", "busy");

  try {
    const format = await (await fetch("/api/audio")).json();

    // The context is created here, inside the click handler, because that is
    // the user gesture browsers require before audio may play. Its sample rate
    // is fixed for the context's whole life, which is why the format was
    // fetched first rather than waited for over the WebSocket.
    const context = new AudioContext({ sampleRate: format.outputSampleRate });
    session.context = context;

    if (Math.round(context.sampleRate) !== format.outputSampleRate) {
      // iOS Safari, mostly. The worklets resample instead; the audio is a
      // little worse and everything still works.
      console.warn(`Asked for ${format.outputSampleRate} Hz, got ${context.sampleRate} Hz. Resampling in the worklet.`);
    }

    await context.audioWorklet.addModule("/worklets.js");

    session.playback = new AudioWorkletNode(context, "playback-processor", {
      processorOptions: { sourceRate: format.outputSampleRate },
    });
    session.playback.port.onmessage = (event) => {
      if (event.data.type === "playing") {
        ui.activity.dataset.speaking = String(event.data.value);
      }
    };
    session.playback.connect(context.destination);

    // The context starts suspended. This is what unlocks it, and it has to
    // happen while the click is still being handled.
    await context.resume();

    setStatus("asking for the microphone", "busy");
    session.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        // The reason this workshop moved audio into the browser. Without it,
        // the agent hears its own voice through the speakers and interrupts
        // itself -- which looks exactly like a broken barge-in implementation.
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
        channelCount: 1,
      },
      video: false,
    });

    session.source = context.createMediaStreamSource(session.stream);
    session.capture = new AudioWorkletNode(context, "capture-processor", {
      processorOptions: {
        targetRate: format.inputSampleRate,
        chunkFrames: format.chunkFrames,
      },
    });
    session.capture.port.onmessage = (event) => {
      const message = event.data;
      if (message.type === "audio") {
        if (session.socket?.readyState === WebSocket.OPEN) {
          session.socket.send(message.buffer);
        }
      } else if (message.type === "level") {
        ui.level.style.width = `${Math.min(100, message.value * 250)}%`;
      }
    };

    // Through a silent gain node rather than straight to the destination. A
    // worklet with no output connection is not reliably pulled by every engine,
    // and connecting it audibly would put the microphone in the speakers.
    const silence = context.createGain();
    silence.gain.value = 0;
    session.source.connect(session.capture).connect(silence).connect(context.destination);

    setStatus("connecting", "busy");
    openSocket();
  } catch (error) {
    setBanner(describe(error));
    setStatus("not connected", "error");
    await teardown();
    ui.connect.disabled = false;
  }
}

/**
 * Turn an exception into something an attendee can act on.
 *
 * @param {unknown} error Whatever was thrown.
 * @returns {string} A sentence for the banner.
 */
function describe(error) {
  if (error && error.name === "NotAllowedError") {
    return "Microphone permission was denied. Allow it in the address bar, then reload.";
  }
  if (error && error.name === "NotFoundError") {
    return "No microphone found. Plug one in or select one in your system settings, then reload.";
  }
  return String(error?.message ?? error);
}

/**
 * Open the WebSocket and route its frames.
 */
function openSocket() {
  const socket = new WebSocket(`ws://${location.host}/ws`);
  socket.binaryType = "arraybuffer";
  session.socket = socket;

  socket.onopen = () => {
    session.connected = true;
    ui.connect.textContent = "Disconnect";
    ui.connect.disabled = false;
    // "My speaker is live." The server waits for this before connecting to
    // Deepgram, so the greeting never arrives before there is anywhere to play
    // it.
    socket.send(JSON.stringify({ type: "start" }));
  };

  socket.onmessage = (event) => {
    if (event.data instanceof ArrayBuffer) {
      session.playback?.port.postMessage({ type: "audio", buffer: event.data }, [event.data]);
      return;
    }
    handleControl(JSON.parse(event.data));
  };

  socket.onerror = () => setBanner("Lost the connection to the Python step. Is it still running?");
  socket.onclose = () => {
    void stop();
  };
}

/**
 * Act on one JSON control message from the server.
 *
 * @param {object} message Parsed frame. Its "type" names the event.
 */
function handleControl(message) {
  switch (message.type) {
    case "status":
      if (message.state === "connected") {
        setStatus("agent connected", "busy");
      } else if (message.state === "closed") {
        setStatus("disconnected", "idle");
      }
      break;

    case "ready":
      // The settings handshake finished. Only now is it worth sending audio:
      // the agent discards anything that arrives before this.
      if (message.capture) {
        session.capture?.port.postMessage({ type: "capture", on: true });
        setStatus("listening", "live");
      } else {
        // An early step that has not wired its microphone up yet. The agent
        // expects a continuous media stream and will hang up after about
        // fifteen seconds of receiving none -- which is the lesson.
        setStatus("connected, not sending audio", "busy");
        setBanner("This step does not send microphone audio yet. The agent will hang up shortly.", "info");
      }
      break;

    case "clear":
      // Barge-in. Everything queued was produced before the user started
      // talking, so playing any of it means talking over them.
      session.playback?.port.postMessage({ type: "clear" });
      break;

    case "transcript":
      addTranscript(message.role, message.content);
      break;

    case "event":
      ui.activity.dataset.event = message.name;
      if (message.name === "AgentThinking") {
        ui.activity.dataset.thinking = "true";
      } else if (message.name === "AgentStartedSpeaking") {
        ui.activity.dataset.thinking = "false";
      }
      break;

    case "latency":
      ui.activity.dataset.latency = `${message.total.toFixed(2)}s`;
      break;

    case "warning":
      setBanner(`${message.code}: ${message.description}`, "info");
      break;

    case "error":
      setBanner(`${message.code}: ${message.description}`);
      setStatus("error", "error");
      break;

    default:
      break;
  }
}

/**
 * Close the socket and tear the audio graph down.
 */
async function stop() {
  if (session.socket && session.socket.readyState === WebSocket.OPEN) {
    session.socket.send(JSON.stringify({ type: "stop" }));
    session.socket.close();
  }
  session.socket = null;
  session.connected = false;
  await teardown();
  ui.connect.textContent = "Connect";
  ui.connect.disabled = false;
  ui.level.style.width = "0%";
  setStatus("not connected", "idle");
}

/**
 * Release the microphone and close the audio context.
 */
async function teardown() {
  session.capture?.port.postMessage({ type: "capture", on: false });
  session.playback?.port.postMessage({ type: "clear" });

  // Stopping the tracks is what clears the browser's recording indicator.
  // Closing the context alone leaves it lit, which attendees notice.
  session.stream?.getTracks().forEach((track) => track.stop());
  session.stream = null;
  session.source = null;
  session.capture = null;
  session.playback = null;

  if (session.context) {
    await session.context.close().catch(() => {});
    session.context = null;
  }
}

ui.connect.addEventListener("click", () => {
  if (session.connected) {
    void stop();
  } else {
    void connect();
  }
});

window.addEventListener("beforeunload", () => {
  session.socket?.close();
});

ui.connect.disabled = !checkSupport();
setStatus("not connected", "idle");
