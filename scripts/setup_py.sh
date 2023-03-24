#!/bin/bash
set -e # Fail if any of the commands below fail.

# Returns "arm64" on m1 devices.
ARCHITECTURE=$(uname -m)

poetry install --with dev

# On arm64 we have to build the tensorflow-io wheel manually.
if [ "$ARCHITECTURE" = "arm64" ]; then
  TENSORFLOW_IO_DIRNAME="./cloned_repos/tensorflow-io"
  rm -rf "$TENSORFLOW_IO_DIRNAME/"
  # We pin the tensorflow-io version to align with the poetry pin in `pyproject.toml`.
  git clone --depth 1 https://github.com/tensorflow/io.git --branch v0.27.0 "$TENSORFLOW_IO_DIRNAME"

  pushd $TENSORFLOW_IO_DIRNAME

  # Activate the poetry virtual env to ensure that we reuse the same dependencies and environment.
  source $(poetry env info --path)/bin/activate

  python setup.py --project tensorflow_io_gcs_filesystem -q bdist_wheel
  python setup.py -q bdist_wheel
  python -m pip install --no-deps dist/tensorflow_io*

  deactivate

  popd
fi

