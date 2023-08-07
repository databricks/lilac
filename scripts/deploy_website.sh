#!/bin/bash

# Fail if any of the commands below fail.
set -e

./scripts/build_docs.sh

pushd docs > /dev/null
firebase deploy
popd > /dev/null
