#!/bin/bash
set -e # Fail if any of the commands below fail.

echo "Linting typescript & javascript..."
npm run lint --workspace src/webSvelte
npm run lint --workspace src/webClientLib

echo "Building typescript..."
npm run check --workspace src/webSvelte
npm run build --workspace src/webSvelte
