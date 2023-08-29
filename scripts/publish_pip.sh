#!/bin/bash
set -e # Fail if any of the commands below fail.

set -o allexport
source .env.local
set +o allexport

if [[ -z "${PYPI_TOKEN}" ]]; then
  echo 'Please set the PYPI_TOKEN variable in your .env.local file'
  exit 1
fi

CUR_BRANCH=$(git rev-parse --abbrev-ref HEAD)

if [[ "$CUR_BRANCH" != "nik-publish" ]]; then
  echo "Please checkout the main branch before publishing."
  exit 1
fi

# Build the web server.
./scripts/build_server_prod.sh

exit 1

poetry version patch

NEW_VERSION=$(poetry version --short)

gh pr create --title "Bump version to $NEW_VERSION" --web

poetry config pypi-token.pypi $PYPI_TOKEN
poetry build

read -p "Continue (y/n)? " CONT
if [ "$CONT" = "y" ]; then
  poetry publish
  echo "Published $(poetry version)"

  echo "Please run ./scripts/tag_version.sh to tag the version after the PR is committed."
else
  echo "Did not publish"
  exit 1
fi

gh release create
