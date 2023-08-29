#!/bin/bash
set -e # Fail if any of the commands below fail.

CUR_BRANCH=$(git rev-parse --abbrev-ref HEAD)

if [[ "$CUR_BRANCH" != "nik-publish" ]]; then
  echo "Please checkout the main branch before publishing."
  exit 1
fi

gh release create
