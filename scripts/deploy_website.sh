#!/bin/bash

# The `firebase` CLI is assumed to be installed.
# See: https://firebase.google.com/docs/cli


# Fail if any of the commands below fail.
set -e

# Load the environment variables from `.env.local`.
set -o allexport
source .env.local set
+o allexport

./scripts/build_docs.sh

pushd docs > /dev/null
# To generate a deploy token, run `firebase login:ci`.
# To deploy to a staging env: firebase hosting:channel:deploy staging
firebase deploy --only hosting --token "$FIREBASE_TOKEN"
popd > /dev/null
