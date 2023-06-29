#!/bin/bash
set -e

poetry export --without-hashes > requirements.txt

DOCKER_TAG="lilac_blueprint:latest"
docker build . --tag $DOCKER_TAG --cache-from $DOCKER_TAG
