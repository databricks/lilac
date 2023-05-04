#!/bin/bash

export NODE_ENV=development

# Make the web client upon bootup to make sure TypeScript files are in sync.
poetry run python -m scripts.make_fastapi_client

# Start the vite devserver.
npm run dev --workspace src/webSvelte -- --open &
pid[2]=$!

# Start the old vite devserver.
npm run dev --workspace src/web &
pid[3]=$!

# Run the node server.
poetry run uvicorn src.server:app --reload --port 5432 --host 0.0.0.0 \
  --reload-dir src --reload-exclude src/web --reload-exclude src/webSvelte &
pid[1]=$!

poetry run watchmedo shell-command \
  --patterns="*.py" \
  --recursive \
  --command='poetry run python -m scripts.make_fastapi_client --api_json_from_server' \
  ./src &
pid[0]=$!

# When control+c is pressed, kill all process ids.
trap "kill ${pid[0]} ${pid[1]} ${pid[2]}; ${pid[3]};  exit 1" INT
wait
