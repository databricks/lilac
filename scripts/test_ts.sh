#!/bin/bash

# Fail if any of the commands below fail.
set -e

npm run test --workspace web
