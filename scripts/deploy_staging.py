"""Deploy local data to a HuggingFace space.

This is used for PR demos during development.

Usage:

poetry run python -m scripts.deploy_staging

Args:
  --hf_space: The huggingface space. Defaults to env.HF_STAGING_DEMO_REPO. Should be formatted like
    `SPACE_ORG/SPACE_NAME`.
  --dataset: [Repeated] The name of a dataset to upload. When not defined, no datasets are uploaded.
  --concept: [Repeated] The name of a concept to upload. When not defined, no local concepts are
    uploaded.
  --skip_ts_build: Skip building the web server TypeScript. Useful to speed up the build if you are
    only changing python or data.
  --skip_cache: Skip uploading the cache files from .cache/lilac which contain cached concept pkl
    files.
  --skip_data_upload: When true, only uploads the wheel + ts files without any other changes.
  --create_space: When true, creates the space if it doesn't exist.
"""

import os
import shutil
import subprocess
from typing import Optional, Union

import click
from huggingface_hub import CommitOperationAdd, CommitOperationDelete, HfApi

from lilac.deploy import PY_DIST_DIR, deploy_project_operations
from lilac.env import env
from lilac.utils import log


@click.command()
@click.option(
  '--hf_space',
  help='The huggingface space. Defaults to env.HF_STAGING_DEMO_REPO. '
  'Should be formatted like `SPACE_ORG/SPACE_NAME`.',
  type=str)
@click.option('--dataset', help='The name of a dataset to upload', type=str, multiple=True)
@click.option(
  '--concept',
  help='The name of a concept to upload. By default all lilac/ concepts are uploaded.',
  type=str,
  multiple=True)
@click.option(
  '--skip_ts_build',
  help='Skip building the web server TypeScript. '
  'Useful to speed up the build if you are only changing python or data.',
  type=bool,
  is_flag=True,
  default=False)
@click.option(
  '--skip_cache_upload',
  help='Skip uploading the cache files from .cache/lilac which contain cached concept pkl models.',
  type=bool,
  is_flag=True,
  default=False)
@click.option(
  '--skip_ts_build',
  help='Skip building the web server TypeScript. '
  'Useful to speed up the build if you are only changing python or data.',
  type=bool,
  is_flag=True,
  default=False)
@click.option(
  '--create_space',
  help='When True, creates the HuggingFace space if it doesnt exist. The space will be created '
  'with the storage type defined by --hf_space_storage.',
  is_flag=True,
  default=False)
@click.option(
  '--skip_data_upload',
  help='When true, only uploads the wheel files without any other changes.',
  is_flag=True,
  default=False)
def deploy_staging(hf_space: Optional[str] = None,
                   dataset: Optional[list[str]] = None,
                   concept: Optional[list[str]] = None,
                   skip_cache_upload: Optional[bool] = False,
                   skip_ts_build: Optional[bool] = False,
                   skip_data_upload: Optional[bool] = False,
                   create_space: Optional[bool] = False) -> None:
  """Generate the huggingface space app."""
  hf_space = hf_space or env('HF_STAGING_DEMO_REPO')
  if not hf_space:
    raise ValueError('Must specify --hf_space or set env.HF_STAGING_DEMO_REPO')

  operations: list[Union[CommitOperationDelete, CommitOperationAdd]] = []

  hf_api = HfApi()

  ##
  ##  Build the web server Svelte & TypeScript.
  ##
  if not skip_ts_build:
    log('Building webserver...')
    run('./scripts/build_server_prod.sh')

  # When datasets are not defined, don't upload any datasets.
  if dataset is None:
    dataset = []
  # When concepts are not defined, don't upload any concepts.
  if concept is None:
    concept = []

  operations.extend(
    deploy_project_operations(
      hf_api,
      # For local deployments, we hard-code the 'data' dir.
      project_dir='data',
      hf_space=hf_space,
      datasets=dataset,
      concepts=concept,
      skip_cache_upload=skip_cache_upload,
      # Never make datasets public when uploading locally.
      make_datasets_public=False,
      skip_data_upload=skip_data_upload,
      hf_space_storage=None,
      create_space=create_space))

  # Unconditionally remove dist. dist is unconditionally uploaded so it is empty when using
  # the public package.
  if os.path.exists(PY_DIST_DIR):
    shutil.rmtree(PY_DIST_DIR)
  os.makedirs(PY_DIST_DIR, exist_ok=True)

  # Build the wheel for pip.
  # We have to change the version to a dev version so that the huggingface demo does not try to
  # install the public pip package.
  current_lilac_version = run('poetry version -s', capture_output=True).stdout.strip()
  # Bump the version temporarily so that the install uses this pip.
  version_parts = current_lilac_version.split('.')
  version_parts[-1] = str(int(version_parts[-1]) + 1)
  temp_new_version = '.'.join(version_parts)

  run(f'poetry version "{temp_new_version}"')
  run('poetry build -f wheel')
  run(f'poetry version "{current_lilac_version}"')

  for upload_file in os.listdir(PY_DIST_DIR):
    operations.append(
      CommitOperationAdd(
        path_in_repo=os.path.join(PY_DIST_DIR, upload_file),
        path_or_fileobj=os.path.join(PY_DIST_DIR, upload_file)))

  # Atomically commit all the operations so we don't kick the server multiple times.
  hf_api.create_commit(
    repo_id=hf_space,
    repo_type='space',
    operations=operations,
    commit_message='Push to HF space',
  )

  log(f'Done! View your space at https://huggingface.co/spaces/{hf_space}')


def run(cmd: str, capture_output=False) -> subprocess.CompletedProcess[str]:
  """Run a command and return the result."""
  return subprocess.run(cmd, shell=True, check=True, capture_output=capture_output, text=True)


if __name__ == '__main__':
  deploy_staging()
