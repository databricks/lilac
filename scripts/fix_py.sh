#!/bin/bash

# Fail if any of the commands below fail.
set -e

# Activate the current py virtual env.
source $(poetry env info --path)/bin/activate

echo "Fixing python with ruff..."
ruff --fix lilacai/

echo "Fixing python imports with isort..."
isort lilacai/

echo "Fixing python formatting with yapf..."
yapf -i -p -r lilacai/
