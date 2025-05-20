#!/bin/bash -ex

# Get version
version=$( (cd .. && poetry version --short))

# Clean build dir
(cd .. && rm -rf dist)

# Build wheel
(cd .. && poetry build)

# Build container
(cd .. && docker build --build-arg version=$version --no-cache -f docker/Dockerfile -t cccs/howler-api:latest -t cccs/howler-api:$version .)
