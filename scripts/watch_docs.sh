#!/bin/bash

# Fail if any of the commands below fail.
set -e

pushd docs > /dev/null

poetry update lilac
poetry install --no-root
# Activate the current py virtual env.
source $(poetry env info --path)/bin/activate

make livehtml

popd > /dev/null
