#!/bin/bash
set -e # Fail if any of the commands below fail.

echo "Linting typescript & javascript..."
npm run lint --workspace src/web

echo "Building typescript..."
npm run build --workspace src/web
