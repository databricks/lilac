#!/bin/bash

# Presubmit script for local development.

# Fail if any of the commands below fail.
set -e

./scripts/lint.sh

./scripts/test.sh

GREEN='\033[1;32m'
NC='\033[0m' # No Color
echo -e "${GREEN}Presubmits passed!${NC}"
