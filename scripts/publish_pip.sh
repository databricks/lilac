#!/bin/bash
set -e # Fail if any of the commands below fail.

set -o allexport
source .env.local
set +o allexport

if [[ -z "${PYPI_TOKEN}" ]]; then
  echo 'Please set the PYPI_TOKEN variable in your .env.local file'
  exit 1
fi

CHANGES=`git status --porcelain`
CUR_BRANCH=`git rev-parse --abbrev-ref HEAD`

if [[ "$CUR_BRANCH" != "nik-publish" ]]; then
  echo "Please checkout the main branch before publishing."
  exit 1
fi

if [ ! -z "$CHANGES" ];
then
    echo "Make sure the main branch has no changes. Found changes:"
    echo $CHANGES
    exit 1
fi

# Build the web server.
./scripts/build_server_prod.sh

exit 1

# Upgrade the version in pyproject.
poetry version patch

NEW_VERSION=`poetry version --short`
NEW_VERSION_ID="v$NEW_VERSION"

# PYPI_TOKEN must be set in .env.local.
poetry config pypi-token.pypi $PYPI_TOKEN

# Build the wheel file.
poetry build

# Publish to pip.

read -p "Continue (y/n)? " CONT
if [ "$CONT" = "y" ]; then
  poetry publish
  echo "Published $(poetry version)"
else
  echo "Did not publish"
  exit 1
fi

# Commit directly to main.
git commit -a -m "Bump version to $NEW_VERSION."
git push origin main

gh release create "$NEW_VERSION_ID" ./dist/*.whl \
  --generate-notes \
  --latest \
  --title "$NEW_VERSION_ID"
