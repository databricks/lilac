#!/bin/bash
set -e # Fail if any of the commands below fail.

echo "Linting typescript & javascript..."
npm run lint --workspace src/web

echo "Building typescript..."
cd src/web && npx tsc --noEmit && cd ../..
npm run build --workspace src/web
