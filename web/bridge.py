"""Run a step's agent, with the browser as its microphone and speaker.

Every step ends the same way:

    bridge.run(settings=SETTINGS, on_message=on_message, on_media=on_media)

which starts a local web server, opens a page, and connects that page's audio to
the step's callbacks. The browser handles the parts that used to need PortAudio:
device selection, permissions, resampling, and -- the reason it is worth doing --
echo cancellation.

    uv run steps/99-final/main.py            # browser
    uv run steps/99-final/main.py --local    # PortAudio, the old way

The server binds to 127.0.0.1 and that is not merely a default. getUserMedia and
AudioWorklet require a secure context; browsers grant that to localhost but not
to a LAN address, so serving this on 192.168.x.x makes the audio API silently
vanish rather than fail.
"""

import argparse
import asyncio
import json
import threading
import time
import webbrowser
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles

from .audio import BrowserPlayer, LocalPlayer, Outbox
from .session import AgentSession, NullReporter, audio_contract

STATIC = Path(__file__).resolve().parent / "static"

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000

StepMessageHandler = Callable[[Any, Any, Any], None]
StepMediaHandler = Callable[[Any, bytes], None]


def run(
    *,
    settings: Any,
    on_message: StepMessageHandler,
    on_media: StepMediaHandler | None = None,
    page: str = "index.html",
    argv: list[str] | None = None,
) -> None:
    """Run a step until the attendee stops it.

    Args:
        settings: The step's AgentV1Settings.
        on_message: Called as on_message(agent, player, message) for every frame
            the agent sends. Raw bytes are audio; everything else is an event.
        on_media: Called as on_media(agent, data) for every captured chunk of
            microphone audio. Omit it in a step that does not send audio yet:
            the browser then never opens the microphone at all.
        page: Which page under web/static to open. Step 1 overrides this.
        argv: Command-line arguments, for testing. Defaults to sys.argv[1:].
    """
    args = _parse_args(argv)

    if args.local:
        _run_local(settings=settings, on_message=on_message, on_media=on_media)
        return

    _run_browser(
        settings=settings,
        on_message=on_message,
        on_media=on_media,
        page=page,
        host=args.host,
        port=args.port,
        open_browser=not args.no_open,
    )


def run_check(*, status: dict[str, Any], argv: list[str] | None = None) -> None:
    """Serve Step 1's browser setup check.

    The same server and the same static directory as run(), minus the agent:
    nothing here opens a Deepgram socket. The page does the audio half of the
    check itself, which is the point -- it exercises exactly the browser code
    path the rest of the workshop uses, rather than a proxy for it.

    Args:
        status: What Python already worked out, served at /api/check and shown
            at the top of the page. Keys: "key_ok" and "key_detail".
        argv: Command-line arguments, for testing. Defaults to sys.argv[1:].
    """
    args = _parse_args(argv)
    url = f"http://{args.host}:{args.port}/check.html"

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        """Announce the URL once the server is accepting connections.

        Args:
            _app: The application. Unused.

        Yields:
            None, for the lifetime of the server.
        """
        print(f"\nFinish the check in your browser: {url}\nPress Ctrl+C when you are done.\n")
        if not args.no_open:
            webbrowser.open(url)
        yield

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)

    @app.get("/api/check")
    async def check() -> dict[str, Any]:
        """Report what the Python half of the check already established.

        Returns:
            The status mapping passed to run_check.
        """
        return status

    app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")

    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Parse the flags every step shares.

    Args:
        argv: Command-line arguments, or None for sys.argv[1:].

    Returns:
        The parsed arguments.
    """
    parser = argparse.ArgumentParser(description="Run this workshop step.")
    parser.add_argument(
        "--local",
        action="store_true",
        help="use the system microphone and speaker via PortAudio instead of a browser",
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"address to serve on (default {DEFAULT_HOST})")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"port to serve on (default {DEFAULT_PORT})")
    parser.add_argument("--no-open", action="store_true", help="do not open a browser window")
    return parser.parse_args(argv)


def _run_browser(
    *,
    settings: Any,
    on_message: StepMessageHandler,
    on_media: StepMediaHandler | None,
    page: str,
    host: str,
    port: int,
    open_browser: bool,
) -> None:
    """Serve the page and bridge its WebSocket to the agent.

    Args:
        settings: The step's AgentV1Settings.
        on_message: The step's message handler.
        on_media: The step's microphone handler.
        page: Which page under web/static to open.
        host: Address to bind.
        port: Port to bind.
        open_browser: Whether to open a browser window on startup.
    """
    url = f"http://{host}:{port}/{page}"

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        """Announce the URL once the server is actually accepting connections.

        Args:
            _app: The application. Unused.

        Yields:
            None, for the lifetime of the server.
        """
        print(f"\nOpen {url}\nPress Ctrl+C to exit.\n")
        if open_browser:
            webbrowser.open(url)
        yield

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)

    # Declared before the static mount: Starlette matches routes in declaration
    # order, and a mount at "/" swallows everything after it.
    @app.get("/api/audio")
    async def audio_format() -> dict[str, int]:
        """Tell the page what audio the agent expects, before it builds a graph.

        An AudioContext's sample rate is fixed at construction, and construction
        has to happen inside the click handler that unlocks it. So the page
        cannot wait for the WebSocket to tell it -- it asks first.

        Returns:
            Sample rates and the microphone chunk size, read from SETTINGS.
        """
        return audio_contract(settings)

    @app.websocket("/ws")
    async def agent_socket(websocket: WebSocket) -> None:
        """Bridge one browser tab to one agent session.

        Args:
            websocket: The browser's connection. Binary frames are microphone
                audio; text frames are JSON control messages.
        """
        await websocket.accept()
        outbox = Outbox(asyncio.get_running_loop())
        session = AgentSession(
            settings=settings,
            on_message=on_message,
            on_media=on_media,
            player=BrowserPlayer(outbox),
            reporter=outbox,
        )

        receiver = asyncio.create_task(_receive(websocket, session))
        pump = asyncio.create_task(_pump(websocket, outbox))
        try:
            _, pending = await asyncio.wait({receiver, pump}, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
        finally:
            # close() joins threads and can block for seconds if the Deepgram
            # socket is already closing. Never inline on the event loop.
            await asyncio.to_thread(session.close)

    app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")

    uvicorn.run(
        app,
        host=host,
        port=port,
        # Not left to uvicorn's import probing. Its preferred implementation
        # imports websockets.legacy, which websockets 17 -- the version
        # deepgram-sdk pins -- no longer ships.
        ws="wsproto",
        log_level="warning",
    )


async def _receive(websocket: WebSocket, session: AgentSession) -> None:
    """Forward browser frames to the session until the socket closes.

    receive_bytes() is unusable here: the ASGI message carries either a "bytes"
    key or a "text" key, and asking for the wrong one raises. So the raw message
    is inspected instead.

    Args:
        websocket: The browser's connection.
        session: The agent session bound to it.
    """
    while True:
        message = await websocket.receive()

        if message["type"] == "websocket.disconnect":
            return
        if message["type"] != "websocket.receive":
            continue

        audio = message.get("bytes")
        if audio is not None:
            session.send_media(audio)
            continue

        text = message.get("text")
        if text is None:
            continue

        payload = json.loads(text)
        if payload.get("type") == "start":
            session.start()
        elif payload.get("type") == "stop":
            return


async def _pump(websocket: WebSocket, outbox: Outbox) -> None:
    """Drain the outbox into the browser, forever.

    Cancelled by the WebSocket handler when the receiver finishes.

    Args:
        websocket: The browser's connection.
        outbox: The queue of frames waiting to be sent.
    """
    while True:
        frame = await outbox.get()
        if isinstance(frame, bytes):
            await websocket.send_bytes(frame)
        else:
            await websocket.send_text(frame)


def _run_local(
    *,
    settings: Any,
    on_message: StepMessageHandler,
    on_media: StepMediaHandler | None,
) -> None:
    """Run the step against the system microphone and speaker.

    The fallback for a machine where the browser path will not do -- a locked
    down browser, no browser at all, or a deliberate look at what the audio
    layer costs when you own it yourself.

    Args:
        settings: The step's AgentV1Settings.
        on_message: The step's message handler.
        on_media: The step's microphone handler.

    Raises:
        TimeoutError: If the agent does not acknowledge settings in time.
    """
    import sounddevice as sd

    input_rate = int(settings.audio.input.sample_rate)
    output_rate = int(settings.audio.output.sample_rate)
    block_size = input_rate * 80 // 1000

    player = LocalPlayer(output_rate)
    player.open()

    session = AgentSession(
        settings=settings,
        on_message=on_message,
        on_media=on_media,
        player=player,
        reporter=NullReporter(),
    )
    session.start()

    ready = threading.Event()

    def wait_ready() -> None:
        """Poll for the settings handshake so the microphone opens after it."""
        deadline = time.monotonic() + 12.0
        while time.monotonic() < deadline:
            if session.ready:
                ready.set()
                return
            time.sleep(0.05)

    wait_ready()
    if not ready.is_set():
        session.close()
        player.close()
        raise TimeoutError("Timed out waiting for agent settings to apply.")

    def microphone_callback(indata: memoryview, _frames: int, _time: object, _status: object) -> None:
        """Forward one captured block of microphone audio to the agent.

        PortAudio invokes this on its own high-priority thread, so the body
        stays a single non-blocking hand-off.

        Args:
            indata: Captured PCM frames. Copied with bytes() because PortAudio
                reuses the underlying memory once this returns.
            _frames: Frame count. Unused.
            _time: PortAudio timing information. Unused.
            _status: PortAudio status flags. Unused.
        """
        session.send_media(bytes(indata))

    # A step with no on_media has nothing to capture into, so the microphone is
    # never opened -- which also means no permission prompt for a step that
    # would not use the answer.
    microphone = None
    if on_media is not None:
        microphone = sd.RawInputStream(
            samplerate=input_rate,
            channels=1,
            dtype="int16",
            blocksize=block_size,
            callback=microphone_callback,
        )
        microphone.start()
        print("\nListening... press Ctrl+C to exit.\n")
    else:
        # The agent expects a continuous media stream and hangs up with
        # CLIENT_MESSAGE_TIMEOUT after about fifteen seconds of receiving none.
        # Steps 2 and 3 send nothing, so that is the expected ending.
        print("\nConnected. This step sends no audio, so the agent will hang up shortly.\n")

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        if microphone is not None:
            microphone.stop()
        session.close()
        player.close()
