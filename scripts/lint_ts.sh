#!/bin/bash
set -e # Fail if any of the commands below fail.

echo "Linting client library..."
npm run lint --workspace web/lib
npm run check --workspace web/lib

echo "Linting svelte project..."
npm run lint --workspace web/blueprint

echo "Building svelte project..."
npm run check --workspace web/blueprint
npm run build --workspace web/blueprint
