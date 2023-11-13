#!/bin/bash

# Fail if any of the commands below fail.
set -e

echo "Fixing python with ruff..."
# ruff --fix fixes lint issues.
poetry run ruff --fix .
# ruff format formats code, organizes imports, etc.
poetry run ruff format .
