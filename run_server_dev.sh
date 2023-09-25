#!/bin/bash

export NODE_ENV=development

# Make the web client upon bootup to make sure TypeScript files are in sync.
poetry run python -m scripts.make_fastapi_client

# Start the vite devserver.
npm run dev --workspace web/blueprint -- --open &
pid[2]=$!

# Run the FastAPI server.
export LILAC_PROJECT_DIR='./data'
poetry run uvicorn lilac.server:app --reload --port 5432 --host 0.0.0.0 \
  --reload-dir lilac &
pid[1]=$!

poetry run watchmedo shell-command \
  --patterns="*.py" \
  --recursive \
  --command='poetry run python -m scripts.make_fastapi_client' \
  ./lilac &
pid[0]=$!

# When control+c is pressed, kill all process ids.
trap "kill ${pid[0]} ${pid[1]} ${pid[2]};  exit 1" INT
wait
