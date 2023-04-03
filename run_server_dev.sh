#!/bin/bash

export NODE_ENV=development

# Start the webpack devserver.
rm -rf dist/ && npm run --prefix src/web dev --watch &
pid[1]=$!

# Run the node server.
poetry run uvicorn src.server:app --reload --port 5432 --host 0.0.0.0 \
  --reload-dir src --reload-exclude src/web &
pid[0]=$!

# When control+c is pressed, kill all process ids.
trap "kill ${pid[0]} ${pid[1]}; exit 1" INT
wait
