#!/bin/bash

# Fail if any of the commands below fail.
set -e

# Activate the current py virtual env.
echo "Linting python with ruff..."
poetry run ruff lilac

poetry run isort --check lilac/

echo "Checking python types with mypy..."
poetry run mypy lilac
