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
# Optional: Add `-v /path/to/test_file.py` to test a single file.
# Optional: Add `-k test_default` to test a single test.
pytest -vv --capture=tee-sys -m "$PYTEST_MARKS"
