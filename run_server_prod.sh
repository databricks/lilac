#!/bin/bash
set -e

# Runs the production server locally, outside a docker image.

./scripts/build_server_prod.sh

# Run the node server.
poetry run uvicorn lilac.server:app --port 5432 --host 0.0.0.0 &
pid[0]=$!

# When control+c is pressed, kill all process ids.
trap "kill ${pid[0]};  exit 1" INT
wait
