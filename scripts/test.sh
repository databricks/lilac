#!/bin/bash

# Fail if any of the commands below fail.
set -e

./scripts/test_ts.sh
./scripts/test_py.sh
