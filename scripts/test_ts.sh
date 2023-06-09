#!/bin/bash

# Fail if any of the commands below fail.
set -e

CI=true npm run test --workspace web/blueprint
CI=true npm run test --workspace web/lib
