# syntax=docker/dockerfile:1.7

# Fully open fallback from standard Docker Hub
FROM python:3.12-alpine AS base

USER root

# Explicitly create the nonroot user to match expected security profiles
RUN addgroup -g 65532 nonroot && \
    adduser -u 65532 -G nonroot -D -H nonroot

RUN mkdir -p /var/lib/howler && \
    mkdir -p /var/log/howler && \
    mkdir -p /var/cache/howler && \
    chmod 750 /var/lib/howler && \
    chmod 770 /var/log/howler && \
    chmod 770 /var/cache/howler && \
    chown nonroot:nonroot /var/lib/howler && \
    chown nonroot:nonroot /var/log/howler && \
    chown nonroot:nonroot /var/cache/howler && \
    chmod g+s /var/lib/howler

WORKDIR /var/lib/howler

# FIX 1: Force Alpine to use plain HTTP repositories to bypass corporate TLS inspection blocks
RUN sed -i 's/https/http/g' /etc/apk/repositories && \
    apk update && \
    apk add --no-cache tzdata && \
    rm -rf /var/cache/apk/*

USER nonroot

# ==========================================
# Builder Stage
# ==========================================
FROM base AS builder

# Keep root privileges to install system packages and global Python modules
USER root

# (Repositories remain HTTP here as it inherits from base)
RUN apk update && apk add --no-cache build-base gcc libffi-dev openssl-dev musl-dev && rm -rf /var/cache/apk/*

# FIX 2: Tell pip to trust PyPI hosts explicitly and be more tolerant of slow links
ENV PIP_TRUSTED_HOST="pypi.org files.pythonhosted.org pypi.python.org python-poetry.org" \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Switch to nonroot before setting up the project dependencies
USER nonroot

# Keep all nonroot tool state under writable app/cache directories.
ENV HOME=/var/lib/howler \
    XDG_CACHE_HOME=/var/cache/howler

# Copy project files (including optional wheels/) before dependency install.
COPY --chown=nonroot:nonroot requirements-main.txt ./
COPY --chown=nonroot:nonroot . .

# Create the app venv and install dependencies.
# Use local wheels when available; otherwise install from package indexes.
RUN --mount=type=cache,target=/var/cache/howler/pip,uid=65532,gid=65532 \
    python -m venv /var/lib/howler/.venv && \
    if [ -d /var/lib/howler/wheels ] && [ "$(ls -A /var/lib/howler/wheels)" ]; then \
        /var/lib/howler/.venv/bin/pip install --find-links=/var/lib/howler/wheels --cache-dir /var/cache/howler/pip --retries 10 --timeout 120 -r /var/lib/howler/requirements-main.txt; \
    else \
        /var/lib/howler/.venv/bin/pip install --cache-dir /var/cache/howler/pip --retries 10 --timeout 120 -r /var/lib/howler/requirements-main.txt; \
    fi



FROM base

# Copy the constructed workspace and virtual environment over
COPY --chown=nonroot:nonroot --from=builder /var/lib/howler/ /var/lib/howler/

USER nonroot

ENV PATH=/var/lib/howler/.venv/bin:$PATH \
    HOME=/var/lib/howler \
    XDG_CACHE_HOME=/var/cache/howler \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/var/lib/howler

EXPOSE 8000

CMD ["python", "howler_mcp/mcp_server/server.py"]