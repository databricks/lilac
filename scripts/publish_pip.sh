#!/bin/bash
set -e # Fail if any of the commands below fail.

set -o allexport
source .env.local
set +o allexport

if [[ -z "${PYPI_TOKEN}" ]]; then
  echo 'Please set the PYPI_TOKEN variable in your .env.local file'
  exit 1
fi

poetry version patch
poetry config pypi-token.pypi $PYPI_TOKEN
poetry build

read -p "Continue (y/n)?" CONT
if [ "$CONT" = "y" ]; then
  poetry publish
  echo "Published $(poetry version)"
else
  echo "Did not publish"
fi
