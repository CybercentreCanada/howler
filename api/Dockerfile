FROM cgr.dev/ssc-spc.gc.ca/python:3.12-dev AS base

USER root

# Must pass the branch and commit as parameter
ARG branch
ARG commit
ARG version

ENV BRANCH=$branch
ENV COMMIT_HASH=$commit
ENV HOWLER_VERSION=$version

# Create howler config directory
RUN mkdir -p /etc/howler && \
    mkdir -p /etc/howler/static && \
    mkdir -p /etc/howler/lookups && \
    chmod 750 /etc/howler && \
    chmod 750 /etc/howler/static && \
    chmod 750 /etc/howler/lookups && \
    chown nonroot:nonroot /etc/howler && \
    chown nonroot:nonroot /etc/howler/static && \
    chown nonroot:nonroot /etc/howler/lookups

# Create howler cache directory
RUN mkdir -p /var/cache/howler
RUN chmod 770 /var/cache/howler
RUN chown nonroot:nonroot /var/cache/howler

# Create howler home directory
RUN mkdir -p /var/lib/howler
RUN chmod 750 /var/lib/howler
RUN chown nonroot:nonroot /var/lib/howler
# Set the setgid bit so files created in here inherit the group
RUN chmod g+s /var/lib/howler
WORKDIR /var/lib/howler

# Create howler log directory
RUN mkdir -p /var/log/howler
RUN chmod 770 /var/log/howler
RUN chown nonroot:nonroot /var/log/howler

# Install common dependancies
RUN apk update && apk add --no-cache zip vim nano && rm -rf /var/cache/apk/*

# Create a temporary image to compile dependencies
FROM base AS builder

# Get required apk packages
RUN apk update && apk add --no-cache build-base gcc libffi-dev openssl-dev && rm -rf /var/cache/apk/*

# Switch user to howler to get predicatable python packages creation
USER nonroot

# Upgrade pip
RUN pip install --no-cache-dir --no-warn-script-location --upgrade pip && rm -rf ~/.cache/pip

# Install poetry
RUN pip install --no-cache-dir --no-warn-script-location poetry && rm -rf ~/.cache/pip
ENV PATH=/var/lib/howler/.local/bin:$PATH

# Install howler into local so it merges new and old packages
COPY . .

RUN python -m poetry install --without dev,test,types,pre-commit --no-interaction

RUN /var/lib/howler/.venv/bin/python /var/lib/howler/howler/external/generate_mitre.py /etc/howler/lookups

RUN pip uninstall poetry -y && rm -rf ~/.cache/pip

# Create a new image, without compile depedencies
FROM base
ARG version
ARG version_tag=${version}

# Get the updated local dir from builder
COPY --chown=nonroot:nonroot --from=builder /var/lib/howler/ /var/lib/howler/
COPY --chown=nonroot:nonroot --from=builder /etc/howler/lookups /etc/howler/lookups
COPY --chown=nonroot:nonroot ./build_scripts/mappings.yml /etc/howler/conf/mappings.yml
COPY --chown=nonroot:nonroot ./static /etc/howler/static/
COPY --chown=nonroot:nonroot ./howler/common/classification.yml /var/lib/howler/.local/lib/python3.12/site-packages/howler/common/

# Setup Environment
ENV PATH=/var/lib/howler/.local/bin:/var/lib/howler/.venv/bin:$PATH
ENV PYTHONPATH=/var/lib/howler/.venv/lib/python3.12/site-packages:/etc/howler/plugins
ENV APP_NAME=howler
ENV APP_PREFIX=hwl
ENV HOWLER_VERSION=${version}
ENV HOWLER_IMAGE_TAG=${version_tag}

ENTRYPOINT ["gunicorn", "howler.patched:app", "--config=python:howler.gunicorn_config", "--worker-class", "gevent"]
