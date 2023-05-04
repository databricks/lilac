#!/bin/bash

# Fail if any of the commands below fail.
set -e

CI=true npm run test --workspace src/webSvelte
CI=true npm run test --workspace src/webClientLib
