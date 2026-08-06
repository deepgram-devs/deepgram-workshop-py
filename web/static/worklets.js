// The two audio processors, in one module. registerProcessor may be called any
// number of times per module, so one addModule() call installs both.
//
// Both run on the audio rendering thread in 128-frame quanta. Nothing here may
// block, allocate carelessly, or throw -- an exception tears the node down and
// the audio simply stops with no obvious cause.
//
// Neither processor assumes the AudioContext runs at the agent's sample rate.
// Chrome and desktop Safari honour `new AudioContext({sampleRate})`, but iOS
// Safari quietly ignores it and can change rate mid-session when a Bluetooth
// headset connects. So both carry a resampler, with an exact fast path for the
// overwhelmingly common case where the rates already match.

const INT16_MIN = -0x8000;
const INT16_MAX = 0x7fff;

/**
 * Captures microphone audio, resamples it to the agent's rate, and posts it
 * upward in fixed-size chunks.
 *
 * The chunk size is the agent's, not the browser's: Flux's turn detection is
 * tuned for 80 ms, and 128-frame quanta are far too small to send individually.
 */
class CaptureProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    const { targetRate, chunkFrames } = options.processorOptions;

    // Input samples consumed per output sample. Exactly 1 when the context is
    // already running at the agent's rate.
    this.ratio = sampleRate / targetRate;
    this.chunkFrames = chunkFrames;
    this.chunk = new Int16Array(chunkFrames);
    this.filled = 0;
    this.position = 0;

    // Off until the server says the settings handshake finished. The agent
    // discards media sent before that, so sending it is pure waste.
    this.capturing = false;

    // The level meter runs whether or not we are capturing -- it is how an
    // attendee confirms their microphone is alive while the handshake is still
    // in flight.
    this.peak = 0;
    this.sinceLevel = 0;

    this.port.onmessage = (event) => {
      if (event.data.type === "capture") {
        this.capturing = event.data.on;
        if (!event.data.on) {
          this.filled = 0;
          this.position = 0;
        }
      }
    };
  }

  /**
   * Append one sample to the outgoing chunk, shipping it when full.
   *
   * @param {number} sample Float sample, nominally -1 to 1.
   */
  push(sample) {
    const clamped = Math.max(-1, Math.min(1, sample));
    this.chunk[this.filled] = clamped < 0 ? clamped * -INT16_MIN : clamped * INT16_MAX;
    this.filled += 1;

    if (this.filled === this.chunkFrames) {
      const buffer = this.chunk.buffer;
      // Transferred, not copied: this thread must not be doing memcpy work it
      // can avoid. The buffer is unusable here afterwards, hence the new one.
      this.port.postMessage({ type: "audio", buffer }, [buffer]);
      this.chunk = new Int16Array(this.chunkFrames);
      this.filled = 0;
    }
  }

  process(inputs) {
    const input = inputs[0][0];
    if (!input) {
      return true;
    }

    for (let i = 0; i < input.length; i += 1) {
      const magnitude = Math.abs(input[i]);
      if (magnitude > this.peak) {
        this.peak = magnitude;
      }
    }
    this.sinceLevel += input.length;
    if (this.sinceLevel >= sampleRate / 20) {
      this.port.postMessage({ type: "level", value: this.peak });
      this.peak = 0;
      this.sinceLevel = 0;
    }

    if (!this.capturing) {
      return true;
    }

    if (this.ratio === 1) {
      for (let i = 0; i < input.length; i += 1) {
        this.push(input[i]);
      }
      return true;
    }

    // Linear interpolation. It aliases above half the target rate without a
    // low-pass ahead of it, which is audible on music and irrelevant on speech.
    // This path only runs where the browser refused to give us the rate we
    // asked for, and the pinned path uses the browser's own resampler.
    while (this.position < input.length) {
      const base = Math.floor(this.position);
      const next = Math.min(base + 1, input.length - 1);
      const fraction = this.position - base;
      this.push(input[base] + (input[next] - input[base]) * fraction);
      this.position += this.ratio;
    }
    this.position -= input.length;

    return true;
  }
}

/**
 * Plays agent audio from a queue that can be thrown away mid-sentence.
 *
 * The queue is the whole point. Audio arrives from the network in bursts and is
 * consumed at a steady 128 frames per quantum, so something has to hold the
 * difference -- and barge-in means being able to discard that something the
 * instant the user starts talking.
 */
class PlaybackProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    const { sourceRate } = options.processorOptions;

    // Source samples consumed per output sample. Exactly 1 when the context is
    // already running at the agent's rate.
    this.ratio = sourceRate / sampleRate;
    this.queue = [];
    this.position = 0;
    this.playing = false;

    this.port.onmessage = (event) => {
      const message = event.data;
      if (message.type === "audio") {
        // Deepgram's chunks are always an even number of bytes; a truncated
        // one would throw here and kill the node, so it is checked.
        if (message.buffer.byteLength % 2 === 0) {
          this.queue.push(new Int16Array(message.buffer));
        }
      } else if (message.type === "clear") {
        this.queue.length = 0;
        this.position = 0;
      }
    };
  }

  process(_inputs, outputs) {
    const output = outputs[0][0];
    let written = 0;

    while (written < output.length && this.queue.length > 0) {
      const head = this.queue[0];
      const base = Math.floor(this.position);

      if (base >= head.length) {
        this.queue.shift();
        this.position -= head.length;
        continue;
      }

      const next = Math.min(base + 1, head.length - 1);
      const fraction = this.position - base;
      const sample = head[base] + (head[next] - head[base]) * fraction;
      output[written] = sample / 32768;
      written += 1;
      this.position += this.ratio;
    }

    // Underrun, or nothing to play. Silence, never a stale buffer.
    while (written < output.length) {
      output[written] = 0;
      written += 1;
    }

    const playing = this.queue.length > 0;
    if (playing !== this.playing) {
      this.playing = playing;
      this.port.postMessage({ type: "playing", value: playing });
    }

    // Always true. Returning false lets the browser garbage-collect the node
    // after one idle quantum, and the next reply would have nowhere to go.
    return true;
  }
}

registerProcessor("capture-processor", CaptureProcessor);
registerProcessor("playback-processor", PlaybackProcessor);
