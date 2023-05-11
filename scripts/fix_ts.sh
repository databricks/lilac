#!/bin/bash
set -e # Fail if any of the commands below fail.

echo "Fixing svelte source..."
npm run format --workspace web/lib
npm run format --workspace web/inspector
