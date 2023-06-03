#!/bin/bash

export NODE_ENV=production

# Run the node server.
poetry run uvicorn src.server:app --port 5432 --host 0.0.0.0 &
pid[0]=$!

# Build the svelte static files and start vite in preview mode.
npm run build --workspace web/blueprint
npm run preview --workspace web/blueprint -- --open &
pid[1]=$!

# When control+c is pressed, kill all process ids.
trap "kill ${pid[0]} ${pid[1]};  exit 1" INT
wait
