#!/bin/bash

# Fail if any of the commands below fail.
set -e

# Activate the current py virtual env.
source $(poetry env info --path)/bin/activate

echo "Testing python using non-github test script..."

PYTEST_MARKS=""
if [ "$CI" ]; then
  # Turn off large download tests in CI so we don't incur github costs.
  PYTEST_MARKS="(not largedownload)"
fi

# Disables log() statements.
export DISABLE_LOGS=True

# -vv enables verbose outputs.
# --capture=tee-sys enables printing for passing tests.
# We propagate the first argument as a test path, which can be:
# 1) `src/data/dataset_test.py` to run a single file.
# 2) `src/data/dataset_test.py::SelectRowsSuite` to run a test suite.
# 3) `src/data/dataset_test.py::SelectRowsSuite::test_columns` to run a single test.
if [ "$1" ]; then
  TEST_PATH="$1"
else
  TEST_PATH="src/"
fi
pytest -vv --capture=tee-sys -m "$PYTEST_MARKS" "$TEST_PATH"
