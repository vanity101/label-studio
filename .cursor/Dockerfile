# Base image for the Label Studio Cloud Agent development environment.
# Installs the stable system toolchains (uv for Python, bun for the frontend).
# Repository dependencies are installed later by .cursor/install.sh after the
# source is checked out.
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        build-essential \
        python3 \
        python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv (Python package/venv manager) system-wide.
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh \
    && uv --version

# Install bun (frontend package manager / JS runtime) system-wide.
ENV BUN_INSTALL=/usr/local
RUN curl -fsSL https://bun.sh/install | bash \
    && bun --version

# ubuntu:24.04 ships a non-root "ubuntu" user (uid 1000); run as it.
USER ubuntu
