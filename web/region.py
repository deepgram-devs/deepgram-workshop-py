"""Which Deepgram hosting location every step talks to.

Deepgram serves the same APIs from more than one place. Global is the default;
EU and AU endpoints exist for rooms that need the audio processed inside a
particular geography. Same API keys, same models, same code -- only the base URL
changes, which is why one line in `.env` is enough to move the whole workshop:

    DEEPGRAM_REGION=global   # api.deepgram.com + agent.deepgram.com (default)
    DEEPGRAM_REGION=eu       # api.eu.deepgram.com
    DEEPGRAM_REGION=au       # api.au.deepgram.com

`.env` is the right home for it. Every step already calls `load_dotenv()`, and
every Deepgram connection in this repo is opened through `deepgram_client()`
below, so setting it once moves Steps 1 through 8 together and no step's code
mentions a region at all. A facilitator running the workshop in Frankfurt or
Sydney edits one line and hands out the same repository.

Two things worth knowing before you switch:

  * The Management API (`/v1/projects`, the call Step 1 makes to prove your key
    works) is global only. It is the control plane, not the speech path, and it
    is the same everywhere -- see `management_client()`.

  * Regional endpoints publish support for `/v1/listen`, `/v2/listen`,
    `/v1/speak`, `/v1/agent/converse`, and `/v1/read`. Newer models reach the
    global endpoint first, so if you are running in EU or AU, connect once with
    your chosen region before the room does.

Reference: https://developers.deepgram.com/reference/regional-endpoints
"""

import os

from deepgram import DeepgramClient
from deepgram.environment import DeepgramClientEnvironment

# What DEEPGRAM_REGION means when it is unset or empty. Global is Deepgram's
# standard endpoint and the one every model reaches first.
DEFAULT_REGION = "global"

# The hosts each region serves from: (REST and STT/TTS host, Voice Agent host).
# Global splits the agent onto its own hostname; the regional endpoints serve
# everything from one, which is the only structural difference between them.
REGION_HOSTS: dict[str, tuple[str, str]] = {
    "global": ("api.deepgram.com", "agent.deepgram.com"),
    "eu": ("api.eu.deepgram.com", "api.eu.deepgram.com"),
    "au": ("api.au.deepgram.com", "api.au.deepgram.com"),
}


def configured_region() -> str:
    """Return the region named in DEEPGRAM_REGION.

    Returns:
        A key of REGION_HOSTS. DEFAULT_REGION when the variable is unset or
        empty, which is the case for anyone who copied `.env.example` and only
        pasted a key.

    Raises:
        ValueError: If DEEPGRAM_REGION names something that is not a Deepgram
            hosting location. Failing here is deliberate: a typo that silently
            fell back to global would send audio to the wrong continent and
            still work, which is the one outcome a regional workshop cannot
            have.
    """
    region = os.getenv("DEEPGRAM_REGION", "").strip().lower() or DEFAULT_REGION

    if region not in REGION_HOSTS:
        options = ", ".join(REGION_HOSTS)
        raise ValueError(
            f"DEEPGRAM_REGION={region!r} is not a Deepgram hosting location. "
            f"Use one of: {options}. Leave it blank or remove it for {DEFAULT_REGION}.",
        )

    return region


def environment(region: str | None = None) -> DeepgramClientEnvironment:
    """Build the SDK environment that points a client at one hosting location.

    The v7 Python SDK takes no `base_url`. Endpoints are described by a
    `DeepgramClientEnvironment` with four fields, one per protocol and service,
    and the SDK joins paths onto them -- so a dedicated or self-hosted Deepgram
    deployment is configured exactly the same way, with its own hostname in
    place of the ones in REGION_HOSTS.

    Args:
        region: A key of REGION_HOSTS, or None to read DEEPGRAM_REGION.

    Returns:
        An environment naming that region's REST, WebSocket, and agent hosts.
    """
    api_host, agent_host = REGION_HOSTS[region or configured_region()]
    return DeepgramClientEnvironment(
        base=f"https://{api_host}",  # REST: listen, speak, read
        production=f"wss://{api_host}",  # STT and TTS WebSockets
        agent=f"wss://{agent_host}",  # Voice Agent WebSocket
        agent_rest=f"https://{agent_host}",  # Voice Agent REST
    )


def deepgram_client(api_key: str, *, region: str | None = None) -> DeepgramClient:
    """Build the Deepgram client every step's agent connection is opened with.

    Args:
        api_key: The key from DEEPGRAM_API_KEY.
        region: A key of REGION_HOSTS, or None to read DEEPGRAM_REGION.

    Returns:
        A client pinned to the configured hosting location.

    Raises:
        ValueError: If DEEPGRAM_REGION names an unknown region.
    """
    return DeepgramClient(api_key=api_key, environment=environment(region))


def management_client(api_key: str) -> DeepgramClient:
    """Build a client pinned to the global endpoint, for the Management API.

    `/v1/projects` and the rest of the Management API live on api.deepgram.com
    whatever region your audio goes to -- the regional endpoints serve the
    speech APIs only, and a management call against one returns 404. Step 1's
    key check is the only thing in this workshop that needs it, and this
    function exists so that stays true on purpose rather than by accident.

    Args:
        api_key: The key from DEEPGRAM_API_KEY.

    Returns:
        A client pinned to Deepgram's global endpoint.
    """
    return DeepgramClient(api_key=api_key, environment=DeepgramClientEnvironment.PRODUCTION)


def describe(region: str | None = None) -> str:
    """Render one region as a line worth printing in a terminal.

    Args:
        region: A key of REGION_HOSTS, or None to read DEEPGRAM_REGION.

    Returns:
        The region name and the agent endpoint it resolves to, for example
        "eu (wss://api.eu.deepgram.com/v1/agent/converse)".
    """
    region = region or configured_region()
    _, agent_host = REGION_HOSTS[region]
    return f"{region} (wss://{agent_host}/v1/agent/converse)"
