#!/bin/bash

# Fail if any of the commands below fail.
set -e

# Activate the current py virtual env.
source $(poetry env info --path)/bin/activate

echo "Linting python with ruff..."
ruff lilac

isort --check lilac/

echo "Checking python types with mypy..."
mypy lilac
