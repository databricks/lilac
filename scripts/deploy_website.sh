#!/bin/bash

# The `firebase` CLI is assumed to be installed.
# See: https://firebase.google.com/docs/cli


# Fail if any of the commands below fail.
set -e

./scripts/build_docs.sh

pushd docs > /dev/null
# To deploy to a staging env: firebase hosting:channel:deploy staging
firebase deploy --only hosting
popd > /dev/null
