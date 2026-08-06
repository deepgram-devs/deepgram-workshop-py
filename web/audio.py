"""Where the agent's voice comes out, and the queue that gets it there.

A step's on_message does two things with audio: it plays what the agent sends,
and it throws away what is already queued when the user interrupts. That is the
whole player interface -- send() and clear() -- and it is deliberately the same
two calls whether the sound comes out of the browser or out of PortAudio.

BrowserPlayer is the default. LocalPlayer is the --local fallback, and is a
direct translation of the sounddevice code this workshop used to ship.
"""

import asyncio
import json
from collections import deque
from typing import Any, Protocol


class Player(Protocol):
    """Somewhere the agent's audio can be played and then unplayed."""

    def send(self, audio: bytes) -> None:
        """Queue one chunk of agent audio for playback.

        Args:
            audio: Raw linear16 PCM at the session's output sample rate.
        """
        ...

    def clear(self) -> None:
        """Discard audio that is queued but not yet heard.

        Called on barge-in. Discarding is the point: anything still queued was
        recorded before the user started talking, and playing it means talking
        over them.
        """
        ...


class Outbox:
    """Frames waiting to go to the browser, oldest first.

    Frames are either bytes (agent audio) or str (a JSON control message). The
    deque is only ever mutated on the event loop thread, which is what makes
    drop_audio() safe: it can walk the queue and remove just the audio without
    racing the pump that is draining it.

    Every public method except get() is callable from any thread.
    """

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        """Bind an outbox to the event loop that will drain it.

        Args:
            loop: The loop running the WebSocket handler.
        """
        self._loop = loop
        self._frames: deque[bytes | str] = deque()
        self._ready = asyncio.Event()

    def put(self, frame: bytes | str) -> None:
        """Queue one frame for the browser, from any thread.

        Args:
            frame: bytes for audio, str for a JSON control message.
        """
        self._loop.call_soon_threadsafe(self._append, frame)

    def send_json(self, **fields: object) -> None:
        """Queue one JSON control message for the browser, from any thread.

        Args:
            **fields: The message body. "type" is required by the browser.
        """
        self.put(json.dumps(fields))

    def drop_audio(self) -> None:
        """Discard every queued audio frame, keeping control messages.

        This is the half of barge-in that is easy to forget. Telling the browser
        to flush its playback buffer does nothing about the seconds of agent
        audio still sitting here: the pump would keep sending it immediately
        afterward and the agent would talk over the user anyway.

        Safe from any thread, and ordered against put(): both hand work to the
        loop with call_soon_threadsafe, which runs callbacks in the order they
        were scheduled. Dropping before queueing a "clear" therefore stays
        dropped-then-cleared.
        """
        self._loop.call_soon_threadsafe(self._drop_audio)

    async def get(self) -> bytes | str:
        """Wait for the next frame and remove it from the queue.

        Must be awaited on the loop this outbox was bound to.

        Returns:
            The oldest queued frame.
        """
        while not self._frames:
            # No await between the clear and the wait, so no callback can
            # append a frame in between and have its set() discarded.
            self._ready.clear()
            await self._ready.wait()
        return self._frames.popleft()

    def _append(self, frame: bytes | str) -> None:
        """Append a frame. Runs on the loop thread.

        Args:
            frame: The frame to queue.
        """
        self._frames.append(frame)
        self._ready.set()

    def _drop_audio(self) -> None:
        """Remove every bytes frame. Runs on the loop thread."""
        kept = [frame for frame in self._frames if not isinstance(frame, bytes)]
        self._frames.clear()
        self._frames.extend(kept)
        if not self._frames:
            self._ready.clear()


class BrowserPlayer:
    """Plays audio by sending it to the browser tab that opened this session."""

    def __init__(self, outbox: Outbox) -> None:
        """Bind a player to a browser connection's outbox.

        Args:
            outbox: The queue drained by the WebSocket pump.
        """
        self._outbox = outbox

    def send(self, audio: bytes) -> None:
        """Queue one chunk of agent audio for the browser to play.

        Args:
            audio: Raw linear16 PCM, forwarded to the page unchanged.
        """
        self._outbox.put(audio)

    def clear(self) -> None:
        """Drop queued audio here and tell the browser to drop its own.

        Order matters: dropping first means the "clear" the browser receives is
        the last audio-related instruction in the stream, with nothing stale
        behind it.
        """
        self._outbox.drop_audio()
        self._outbox.send_json(type="clear")


class LocalPlayer:
    """Plays audio through the default system output device via PortAudio.

    The --local fallback. sounddevice is imported lazily so that the default
    browser path does not need PortAudio present at all -- which is most of the
    reason the browser path exists.
    """

    def __init__(self, sample_rate: int, channels: int = 1) -> None:
        """Describe the stream without opening it yet.

        Args:
            sample_rate: Output sample rate in hertz.
            channels: Output channel count.
        """
        self._sample_rate = sample_rate
        self._channels = channels
        # Any, not a PortAudio type: sounddevice is imported lazily so the
        # default browser path never needs it installed, and naming its types
        # here would undo that.
        self._stream: Any = None

    def open(self) -> None:
        """Open and start the output stream.

        Raises:
            RuntimeError: If sounddevice or PortAudio is unavailable, which on
                the --local path is fatal and worth saying plainly.
        """
        try:
            import sounddevice as sd
        except OSError as error:  # PortAudio missing or no audio backend
            raise RuntimeError(
                f"--local needs a working PortAudio install: {error}. Drop the flag to use the browser instead.",
            ) from error

        self._stream = sd.RawOutputStream(
            samplerate=self._sample_rate,
            channels=self._channels,
            dtype="int16",
        )
        self._stream.start()

    def send(self, audio: bytes) -> None:
        """Write one chunk of agent audio to the speaker.

        Args:
            audio: Raw linear16 PCM at this stream's sample rate.
        """
        import sounddevice as sd

        if self._stream is None:
            return
        try:
            self._stream.write(audio)
        except sd.PortAudioError as error:
            # Dropping a chunk beats ending the call. This runs inside the
            # SDK's receive loop, which reports any escaping exception as
            # EventType.ERROR and closes the connection.
            print(f">> Dropped audio chunk: {error}")

    def clear(self) -> None:
        """Discard PortAudio's queued output, then restart the stream.

        abort() throws the queue away; stop() would drain it, which is exactly
        the audio barge-in exists to suppress.
        """
        import sounddevice as sd

        if self._stream is None:
            return
        try:
            self._stream.abort()
            self._stream.start()
        except sd.PortAudioError as error:
            print(f">> Barge-in failed: {error}")

    def close(self) -> None:
        """Stop the output stream if it was opened."""
        if self._stream is not None:
            self._stream.stop()
            self._stream = None
