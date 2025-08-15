FROM python:3.12-alpine AS base

# Make sure root account is locked so 'su' commands fail all the time
RUN passwd -l root

# Add howler user
RUN useradd -b /var/lib -U -m howler

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
    chown howler:howler /etc/howler && \
    chown howler:howler /etc/howler/static && \
    chown howler:howler /etc/howler/lookups

# Create howler cache directory
RUN mkdir -p /var/cache/howler
RUN chmod 770 /var/cache/howler
RUN chown howler:howler /var/cache/howler

# Create howler home directory
RUN mkdir -p /var/lib/howler
RUN chmod 750 /var/lib/howler
RUN chown howler:howler /var/lib/howler
WORKDIR /var/lib/howler

# Create howler log directory
RUN mkdir -p /var/log/howler
RUN chmod 770 /var/log/howler
RUN chown howler:howler /var/log/howler

# Install common dependancies
RUN apk add libsasl zip vim nano

# Create a temporary image to compile dependencies
FROM base AS builder
ARG version=*

# Upgrade pip
RUN pip install --no-cache-dir --no-warn-script-location --upgrade pip && rm -rf ~/.cache/pip

# Switch user to howler to get predicatable python packages creation
USER howler

# Create a snpshot file so we know what to copy
RUN touch /tmp/before-pip

# Install howler into local so it merges new and old packages
COPY dist* dist/

RUN pip install --no-cache-dir --no-warn-script-location --user dist/howler_api-*-py3-none-any.whl && \
    rm -rf ~/.cache/pip && \
    python /var/lib/howler/.local/lib/python3.12/site-packages/howler/external/generate_mitre.py /etc/howler/lookups

# Remove files that existed before the pip install so that our copy command below doesn't take a snapshot of
# files that already exist in the base image
RUN find /var/lib/howler/.local -type f ! -newer /tmp/before-pip -delete

# Create a new image, without compile depedencies
FROM base
ARG version=0.0.0.dev0
ARG version_tag=${version}

# Get the updated local dir from builder
COPY --chown=howler:howler --from=builder /var/lib/howler/.local /var/lib/howler/.local
COPY --chown=howler:howler --from=builder /etc/howler/lookups /etc/howler/lookups
COPY --chown=howler:howler ./build_scripts/mappings.yml /etc/howler/conf/mappings.yml
COPY --chown=howler:howler ./static /etc/howler/static/
COPY --chown=howler:howler ./howler/common/classification.yml /var/lib/howler/.local/lib/python3.12/site-packages/howler/common/

# Setup Environment
ENV PATH=/var/lib/howler/.local/bin:$PATH
ENV PYTHONPATH=/var/lib/howler/.local/lib/python3.12/site-packages:/etc/howler/plugins
ENV APP_NAME=howler
ENV APP_PREFIX=hwl
ENV HOWLER_VERSION=${version}
ENV HOWLER_IMAGE_TAG=${version_tag}

# Switch back to howler and run the app
USER howler

CMD ["gunicorn", "howler.patched:app", "--config=python:howler.gunicorn_config", "--worker-class", "gevent"]
