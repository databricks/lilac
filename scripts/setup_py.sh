#!/bin/bash
set -e # Fail if any of the commands below fail.

poetry lock --no-update
poetry install --with dev --all-extras
