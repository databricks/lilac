#!/bin/bash

# Fail if any of the commands below fail.
set -e

lilac hf-docker-start
gunicorn lilac.server:app \
  --bind 0.0.0.0:5432 \
  --preload -k uvicorn.workers.UvicornWorker \
  --timeout 120
