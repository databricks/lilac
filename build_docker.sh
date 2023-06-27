#!/bin/bash
set -e

# TODO(nsthorat): Remove dev deps.
poetry export --without-hashes > requirements.txt

DOCKER_TAG="lilac_blueprint:latest"

docker build . --tag $DOCKER_TAG --cache-from $DOCKER_TAG
