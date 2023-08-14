#!/bin/bash

# Fail if any of the commands below fail.
set -e

python docker_start.py
gunicorn lilac.server:app \
  --bind 0.0.0.0:5432 \
  --preload -k uvicorn.workers.UvicornWorker \
  --timeout 120
