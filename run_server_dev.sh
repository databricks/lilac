#!/bin/bash

set -e
export NODE_ENV=development

# Make the web client upon bootup to make sure TypeScript files are in sync.
poetry run python -m scripts.make_fastapi_client

# Start the vite devserver.
npm run dev --workspace web/blueprint -- --open &
pid[2]=$!

# Run the FastAPI server.
if [ "$1" ]; then
  export LILAC_PROJECT_DIR="$1"
else
  export LILAC_PROJECT_DIR="./data"
fi
poetry run uvicorn lilac.server:app --reload --port 5432 --host 0.0.0.0 \
  --reload-dir lilac &
pid[1]=$!

poetry run watchmedo auto-restart \
  --patterns="*.py" \
  --debounce-interval=1 \
  --no-restart-on-command-exit \
  --recursive \
  --directory=lilac \
  poetry -- -- run python -m scripts.make_fastapi_client &
pid[0]=$!

# When control+c is pressed, kill all process ids.
trap "pkill -P $$;  exit 1" INT
wait
