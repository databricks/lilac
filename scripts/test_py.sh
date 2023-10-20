#!/bin/bash

# Fail if any of the commands below fail.
set -e

echo "Testing python using non-github test script..."

PYTEST_MARKS=""
if [ "$CI" ]; then
  # Turn off large download tests in CI so we don't incur github costs.
  PYTEST_MARKS="(not largedownload)"
fi

export LILAC_TEST=True

# -vv enables verbose outputs.
# --capture=tee-sys enables printing for passing tests.
# We propagate the first argument as a test path, which can be:
# 1) `lilac/data/dataset_test.py` to run a single file.
# 2) `lilac/data/dataset_test.py::SelectRowsSuite` to run a test suite.
# 3) `lilac/data/dataset_test.py::SelectRowsSuite::test_columns` to run a single test.
if [ "$1" ]; then
  TEST_PATH="$1"
else
  TEST_PATH="lilac/"
fi
poetry run pytest -vv --capture=tee-sys -m "$PYTEST_MARKS" "$TEST_PATH"
