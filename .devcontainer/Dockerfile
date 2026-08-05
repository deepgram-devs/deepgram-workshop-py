# Python 3.13 to match requires-python in pyproject.toml.
FROM mcr.microsoft.com/devcontainers/python:2-3.13-bookworm

# sounddevice binds to PortAudio, and PortAudio looks for ALSA. Installing them
# here means the audio stack is present even though the container may have no
# device to point it at -- see .devcontainer/README.md. libasound2-plugins is
# what bridges ALSA to PulseAudio when a host does share its audio.
#
# The yarn.list line comes with the base image and its signing key no longer
# verifies, which fails `apt-get update` outright. Nothing here needs yarn, so
# drop the source rather than work around the GPG error.
RUN rm -f /etc/apt/sources.list.d/yarn.list \
    && apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get install -y --no-install-recommends \
        libportaudio2 \
        libasound2-plugins \
        alsa-utils \
        pulseaudio-utils \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Pinned so every attendee resolves uv.lock with the same resolver.
COPY --from=ghcr.io/astral-sh/uv:0.11.21 /uv /uvx /usr/local/bin/

# The workspace is a bind mount from the host, which may already hold a .venv
# built for macOS or Windows. Keeping the container's environment outside the
# workspace means the two never argue -- and `uv run` still finds it.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PATH=/opt/venv/bin:$PATH

RUN mkdir -p /opt/venv && chown vscode:vscode /opt/venv
