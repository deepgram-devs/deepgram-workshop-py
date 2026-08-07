"""One live agent session: the Deepgram socket, its threads, and the browser.

The Deepgram SDK's agent socket is synchronous and blocking. The web server is
asyncio. Everything awkward about gluing those together lives in this file, and
none of it leaks into the steps.

Three threads per session, plus the event loop:

    listener  runs socket.start_listening(), fires on_message
    sender    the only thread that ever writes to the Deepgram socket
    worker    opens the connection, owns the other two, tears them all down

The sender thread exists for a specific reason. websockets' send() joins the
receive thread with close_timeout -- ten seconds by default, and the SDK never
overrides it -- the moment the connection starts closing. In the old PortAudio
version that stalled an audio callback and dropped some frames. On an event
loop it would freeze the entire server, including every other tab. So no
coroutine ever calls send directly; it queues, and one thread takes the risk.
"""

import os
import queue
import threading
from collections.abc import Callable
from typing import Any, Protocol

from deepgram.core.events import EventType

from .audio import Player
from .region import DEFAULT_REGION, configured_region, deepgram_client, describe

# About twenty seconds of microphone audio. Reaching this means the Deepgram
# socket has stopped draining -- the connection is dying and the backlog is
# already worthless, so the newest chunk is dropped rather than growing a queue
# nobody will ever hear.
SEND_QUEUE_MAX = 256

# How long to wait for SettingsApplied before giving up, in seconds. Matches the
# timeout the CLI version used.
SETTINGS_TIMEOUT = 10.0

_STOP = object()


class AgentHandle:
    """The `agent` a step's callbacks are given: sends, minus the blocking.

    Method-for-method identical to the SDK's socket client for everything the
    workshop uses, so `agent.send_media(data)` and
    `agent.send_function_call_response(...)` in a step mean exactly what they
    look like. The difference is that they return immediately: the call is
    handed to the sender thread instead of being written to the socket here.
    """

    def __init__(self, socket: Any, outbound: queue.Queue) -> None:
        """Wrap a connected socket.

        Args:
            socket: The SDK's V1SocketClient.
            outbound: The queue the sender thread drains.
        """
        self._socket = socket
        self._outbound = outbound

    def send_media(self, audio: bytes) -> None:
        """Send one chunk of microphone audio to the agent.

        Args:
            audio: Raw linear16 PCM at the session's input sample rate.
        """
        self._enqueue("send_media", audio)

    def send_settings(self, settings: Any) -> None:
        """Send the settings handshake.

        Args:
            settings: An AgentV1Settings.
        """
        self._enqueue("send_settings", settings)

    def send_function_call_response(self, response: Any) -> None:
        """Return the result of a client-side function call.

        Args:
            response: An AgentV1SendFunctionCallResponse.
        """
        self._enqueue("send_function_call_response", response)

    def _enqueue(self, method: str, payload: Any) -> None:
        """Hand one send to the sender thread.

        Args:
            method: Name of the socket method to call.
            payload: Its single argument.
        """
        try:
            self._outbound.put_nowait((method, payload))
        except queue.Full:
            print(">> Send queue full, dropping a chunk -- the connection is not draining.")


class Reporter(Protocol):
    """Somewhere session events can be surfaced to a user interface."""

    def send_json(self, **fields: object) -> None:
        """Report one event.

        Args:
            **fields: The message body. "type" names the event.
        """
        ...


class NullReporter:
    """Reports nothing. The --local path, where the terminal is the interface."""

    def send_json(self, **fields: object) -> None:
        """Discard one event.

        Args:
            **fields: Ignored.
        """


class AgentSession:
    """A Deepgram agent connection, wherever its audio happens to come out.

    Identical for the browser and for --local: only the player and the reporter
    differ, and neither one knows how the connection is managed.

    Args:
        settings: The step's AgentV1Settings. Also the source of truth for the
            audio contract reported to the browser.
        on_message: The step's message handler, called as
            on_message(agent, player, message) for every inbound frame.
        on_media: The step's microphone handler, called as on_media(agent, data)
            for every captured chunk, or None in a step that sends no audio
            yet. None keeps the microphone closed rather than capturing into a
            void -- and lets the agent's CLIENT_MESSAGE_TIMEOUT show up on
            schedule, which is a lesson in Steps 2 and 3.
        player: Where agent audio is played, and un-played on barge-in.
        reporter: Where session events are surfaced, or NullReporter().
    """

    def __init__(
        self,
        *,
        settings: Any,
        on_message: Callable[[Any, Any, Any], None],
        on_media: Callable[[Any, bytes], None] | None,
        player: Player,
        reporter: Reporter,
    ) -> None:
        """Build a session without connecting to anything yet."""
        self._settings = settings
        self._on_message = on_message
        self._on_media = on_media
        self._player = player
        self._reporter = reporter

        self._outbound: queue.Queue = queue.Queue(maxsize=SEND_QUEUE_MAX)
        self._handle: AgentHandle | None = None
        self._socket: Any = None
        self._worker: threading.Thread | None = None
        self._settings_applied = threading.Event()
        self._closing = threading.Event()

    @property
    def ready(self) -> bool:
        """Whether the settings handshake has completed.

        Returns:
            True once SettingsApplied has arrived. Media sent before this is
            discarded by the agent, so the browser is told to wait for it.
        """
        return self._settings_applied.is_set()

    def start(self) -> None:
        """Connect to Deepgram on a background thread and begin the handshake."""
        self._worker = threading.Thread(target=self._run, name="agent-worker", daemon=True)
        self._worker.start()

    def send_media(self, audio: bytes) -> None:
        """Forward one microphone chunk from the browser to the step.

        Chunks that arrive before the handshake completes are dropped: the agent
        would discard them anyway, and dropping them here keeps the step's
        callback a straight line.

        Args:
            audio: Raw linear16 PCM from the browser's capture worklet.
        """
        if self._on_media is None or self._handle is None or not self.ready:
            return
        self._on_media(self._handle, audio)

    def close(self) -> None:
        """Close the Deepgram socket and wait for the threads to unwind.

        Blocking, on purpose -- it joins the worker. Call it with
        asyncio.to_thread, never inline on the event loop.
        """
        self._closing.set()
        socket = self._socket
        if socket is not None:
            # V1SocketClient exposes no close(). The underlying websockets
            # Connection is the only handle there is, and closing it is what
            # ends start_listening's iteration. Deliberate reach into a private
            # attribute; revisit if the SDK grows a public close.
            try:
                socket._websocket.close()
            except Exception as error:  # noqa: BLE001 -- already shutting down
                print(f">> Error closing agent socket: {error}")
        if self._worker is not None:
            self._worker.join(timeout=5.0)

    def _run(self) -> None:
        """Own the connection for its whole life. Runs on the worker thread."""
        api_key = os.getenv("DEEPGRAM_API_KEY", "").strip()
        if not api_key:
            self._fail(
                "DEEPGRAM_API_KEY is empty. Put your key in .env at the repo root, then "
                "restart. Get one at https://console.deepgram.com/signup?jump=keys",
            )
            return

        # Where this connection goes is DEEPGRAM_REGION's business, not the
        # step's -- see web/region.py. An unusable value fails here rather than
        # quietly falling back to global.
        try:
            region = configured_region()
            client = deepgram_client(api_key, region=region)
        except ValueError as error:
            self._fail(str(error))
            return

        if region != DEFAULT_REGION:
            print(f">> Region: {describe(region)}")

        sender: threading.Thread | None = None

        try:
            with client.agent.v1.connect() as socket:
                self._socket = socket
                handle = AgentHandle(socket, self._outbound)
                self._handle = handle

                socket.on(EventType.OPEN, lambda _: self._on_open())
                socket.on(EventType.MESSAGE, lambda message: self._dispatch(handle, message))
                socket.on(EventType.CLOSE, lambda _: print(">> Connection closed"))
                socket.on(EventType.ERROR, lambda error: print(f">> Error: {error}"))

                listener = threading.Thread(target=socket.start_listening, name="agent-listener", daemon=True)
                listener.start()

                sender = threading.Thread(target=self._send_loop, args=(socket,), name="agent-sender", daemon=True)
                sender.start()

                print("Sending agent settings...")
                handle.send_settings(self._settings)

                if not self._settings_applied.wait(SETTINGS_TIMEOUT):
                    self._fail("Timed out waiting for agent settings to apply.")
                    return

                # start_listening returns when the socket closes, whether that
                # is the browser hanging up, Deepgram dropping us, or an error.
                listener.join()
        except Exception as error:  # noqa: BLE001 -- reported to the browser, not raised into asyncio
            if not self._closing.is_set():
                self._fail(str(error))
        finally:
            self._outbound.put(_STOP)
            if sender is not None:
                sender.join(timeout=2.0)
            self._reporter.send_json(type="status", state="closed")

    def _send_loop(self, socket: Any) -> None:
        """Drain the outbound queue into the socket. Runs on the sender thread.

        Args:
            socket: The connected V1SocketClient.
        """
        while True:
            item = self._outbound.get()
            if item is _STOP:
                return
            method, payload = item
            try:
                getattr(socket, method)(payload)
            except Exception as error:  # noqa: BLE001 -- a dead socket is the close path's problem
                if not self._closing.is_set():
                    print(f">> Send failed ({method}): {error}")
                return

    def _on_open(self) -> None:
        """Report the open connection to the terminal and the interface."""
        print(">> Connection opened")
        self._reporter.send_json(type="status", state="connected")

    def _dispatch(self, handle: AgentHandle, message: Any) -> None:
        """Mirror one agent message to the interface, then hand it to the step.

        Runs on the SDK's listener thread -- the same thread the old PortAudio
        version used, which is what keeps the threading warning in a step's
        handle_function_call docstring true.

        Args:
            handle: The agent handle passed to the step's callback.
            message: Raw bytes of agent audio, or a decoded event model.
        """
        if not isinstance(message, bytes):
            self._mirror(message)
        try:
            self._on_message(handle, self._player, message)
        except Exception as error:  # noqa: BLE001 -- a step bug should not kill the call
            print(f">> Error in step's on_message: {error}")

    def _mirror(self, message: Any) -> None:
        """Forward one event to the browser as a JSON control frame.

        The step keeps its prints; this is what puts the same information on
        screen. Steps therefore need no browser-specific code to get a live
        transcript.

        Args:
            message: A decoded event model with a "type" attribute.
        """
        message_type = getattr(message, "type", "Unknown")

        if message_type == "SettingsApplied":
            self._settings_applied.set()
            self._reporter.send_json(type="ready", capture=self._on_media is not None)
        elif message_type == "ConversationText":
            self._reporter.send_json(
                type="transcript",
                role=getattr(message, "role", "unknown"),
                content=getattr(message, "content", ""),
            )
        elif message_type in {"UserStartedSpeaking", "AgentThinking", "AgentStartedSpeaking", "AgentAudioDone"}:
            self._reporter.send_json(type="event", name=message_type)
        elif message_type == "LatencyReport":
            total = getattr(message, "total_latency", None)
            if total is not None:
                self._reporter.send_json(type="latency", total=total)
        elif message_type in {"Error", "Warning"}:
            self._reporter.send_json(
                type=message_type.lower(),
                code=getattr(message, "code", "unknown"),
                description=getattr(message, "description", ""),
            )

    def _fail(self, detail: str) -> None:
        """Report a fatal session problem to the terminal and the browser.

        Args:
            detail: A message written for the attendee reading it in a red box.
        """
        print(f">> {detail}")
        self._reporter.send_json(type="error", code="session", description=detail)


def audio_contract(settings: Any) -> dict[str, int]:
    """Read the browser's audio format out of the step's settings.

    SETTINGS stays the single source of truth: a rate changed in a step reaches
    the capture and playback worklets without anyone touching JavaScript.

    Args:
        settings: An AgentV1Settings.

    Returns:
        Sample rates for capture and playback, and the microphone chunk size in
        frames. Fern types these fields as float; the browser wants integers.
    """
    audio = settings.audio
    input_rate = int(audio.input.sample_rate)
    output_rate = int(audio.output.sample_rate)
    return {
        "inputSampleRate": input_rate,
        "outputSampleRate": output_rate,
        # 80 ms per chunk, the size Flux's turn detection is tuned for. Smaller
        # adds websocket overhead; larger delays turn detection.
        "chunkFrames": input_rate * 80 // 1000,
    }
