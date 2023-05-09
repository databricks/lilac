#!/bin/bash
set -e # Fail if any of the commands below fail.

echo "Linting client library..."
npm run lint --workspace src/webClientLib
npm run check --workspace src/webClientLib

echo "Linting svelte project..."
npm run lint --workspace src/webSvelte

echo "Building svelte project..."
npm run check --workspace src/webSvelte
npm run build --workspace src/webSvelte
