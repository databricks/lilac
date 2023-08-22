#!/bin/bash
set -e

# Make the FastAPI client typescript.
poetry run python -m scripts.make_fastapi_client

# Build the svelte static files.
rm -rf web/blueprint/build
npm run build --workspace web/blueprint

rm -rf lilac/web && mkdir -p lilac/web
cp -R web/blueprint/build/* lilac/web/
