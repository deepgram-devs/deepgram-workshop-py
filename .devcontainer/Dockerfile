# The workshop's container image: Python 3.13 plus uv, and nothing else it does
# not already need.
#
# The base is Microsoft's dev container image rather than python:3.13-slim
# because it already carries the parts a workshop attendee will otherwise ask
# about ten minutes in -- git, curl, a non-root `vscode` user, and a shell with
# history that survives a rebuild.
FROM mcr.microsoft.com/devcontainers/python:1-3.13-bookworm

# uv ships as a single static binary in its own image, so this is a copy rather
# than an install script: no network fetch at build time, no PATH surprises, and
# the version is whatever tag you name here. Pin it (ghcr.io/astral-sh/uv:0.9.7)
# if you are running a workshop and want every laptop on the same uv.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# uv's default hardlink strategy warns loudly when its cache and the target
# environment sit on different filesystems, which is exactly the shape of a bind
# -mounted workspace. Copying instead costs a few seconds once and removes a
# warning that reads like an error.
ENV UV_LINK_MODE=copy
