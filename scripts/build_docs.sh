#!/bin/bash

# Fail if any of the commands below fail.
set -e

pushd docs > /dev/null

poetry update lilac
poetry install
# Activate the current py virtual env.
source $(poetry env info --path)/bin/activate

rm -rf _build
make html

popd > /dev/null
deactivate
