#!/bin/bash
set -e

# Make the FastAPI client typescript.
poetry run python -m scripts.make_fastapi_client

# Build the svelte static files.
npm run build --workspace web/blueprint
