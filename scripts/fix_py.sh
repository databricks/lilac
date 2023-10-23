#!/bin/bash

# Fail if any of the commands below fail.
set -e

echo "Fixing python with ruff..."
poetry run ruff --fix lilac/

echo "Fixing python imports with isort..."
poetry run isort lilac/

echo "Fixing python formatting with yapf..."
poetry run yapf -i -p -r lilac/
