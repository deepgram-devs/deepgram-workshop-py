"""The browser bridge: the parts of this workshop that are never an exercise.

Each step under steps/ owns the agent -- its settings, its message handling, its
functions. This package owns the plumbing underneath: a local web server, one
WebSocket to the browser, and the threads that keep a blocking Deepgram socket
from stalling an asyncio event loop.

Attendees read this. They do not edit it.

AgentHandle and Player are re-exported because every step's callbacks are handed
one of each. Naming them in a step's signatures is what turns `agent.send_media`
and `player.clear` into things an editor can complete and a type checker can
check, rather than attributes of a bare `object`.
"""

from .audio import Player
from .session import AgentHandle

__all__ = ["AgentHandle", "Player"]
