"""Deploys the public HuggingFace demo to https://huggingface.co/spaces/lilacai/lilac.

This script will, in order:
1) Sync from the HuggingFace space data (only datasets). (--skip_sync to skip syncing)
2) Load the data from the demo.yml config. (--skip_load to skip loading)
3) Build the web server TypeScript. (--skip_build to skip building)
4) Push code & data to the HuggingFace space.

Usage:
poetry run python -m scripts.deploy_demo \
  --data_dir=./demo_data \
  --config=./demo.yml \
  --hf_space=lilacai/lilac

Add:
  --skip_sync to skip syncing data from the HuggingFace space data.
  --skip_load to skip loading the data.
  --skip_build to skip building the web server TypeScript.
  --skip_deploy to skip deploying to HuggingFace. Useful to test locally.
"""
import os
import shutil
import subprocess

import click
import huggingface_hub

from lilac.concepts.db_concept import CONCEPTS_DIR
from lilac.db_manager import list_datasets
from lilac.load import load
from lilac.utils import get_datasets_dir

from .deploy_hf import deploy_hf


@click.command()
@click.option('--config', help='The Lilac config path.', type=str)
@click.option('--hf_space', help='The huggingface space.', type=str)
@click.option('--data_dir', help='The local output dir to use to sync the data.', type=str)
@click.option(
  '--overwrite',
  help='When True, runs all all data from scratch, overwriting existing data. When false, only'
  'load new datasets, embeddings, and signals.',
  type=bool,
  is_flag=True,
  default=False)
@click.option(
  '--skip_sync',
  help='Skip syncing data from the HuggingFace space data.',
  type=bool,
  is_flag=True,
  default=False)
@click.option('--skip_load', help='Skip loading the data.', type=bool, is_flag=True, default=False)
@click.option(
  '--skip_build',
  help='Skip building the web server TypeScript. '
  'Useful to speed up the build if you are only changing python or data.',
  type=bool,
  is_flag=True,
  default=False)
@click.option(
  '--skip_deploy',
  help='Skip deploying to HuggingFace. Useful to test locally.',
  type=bool,
  is_flag=True,
  default=False)
def deploy_demo(config: str, hf_space: str, data_dir: str, overwrite: bool, skip_sync: bool,
                skip_load: bool, skip_build: bool, skip_deploy: bool) -> None:
  """Deploys the public demo."""
  if not skip_sync:
    repo_basedir = os.path.join(data_dir, '.hf_sync')
    shutil.rmtree(repo_basedir, ignore_errors=True)

    huggingface_hub.snapshot_download(
      repo_id=hf_space, repo_type='space', local_dir=repo_basedir, local_dir_use_symlinks=False)

    shutil.rmtree(get_datasets_dir(data_dir), ignore_errors=True)
    shutil.move(get_datasets_dir(os.path.join(repo_basedir, 'data')), data_dir)

  if not skip_load:
    load(data_dir, config, overwrite)

  if not skip_deploy:
    datasets = [f'{d.namespace}/{d.dataset_name}' for d in list_datasets(data_dir)]
    deploy_hf(
      # Take this from the env variable.
      hf_username=None,
      hf_space=hf_space,
      datasets=datasets,
      # No extra concepts. lilac concepts are pushed by default.
      concepts=[],
      skip_build=skip_build,
      skip_cache=False,
      data_dir=data_dir)


def run(cmd: str) -> subprocess.CompletedProcess[bytes]:
  """Run a command and return the result."""
  return subprocess.run(cmd, shell=True, check=True)


if __name__ == '__main__':
  deploy_demo()
