"""Deploys the public HuggingFace demo to https://huggingface.co/spaces/lilacai/lilac.

This script will, in order:
1) Sync from the HuggingFace space data (only datasets). (--skip_sync to skip syncing)
2) Load the data from the lilac_hf_space.yml config. (--skip_load to skip loading)
3) Build the web server TypeScript. (--skip_build to skip building)
4) Push code & data to the HuggingFace space.

Usage:
poetry run python -m scripts.deploy_demo \
  --data_dir=./demo_data \
  --config=./lilac_hf_space.yml \
  --hf_space=lilacai/lilac \
  --make_datasets_public

Add:
  --skip_sync to skip syncing data from the HuggingFace space data.
  --skip_load to skip loading the data.
  --skip_build to skip building the web server TypeScript.
  --skip_deploy to skip deploying to HuggingFace. Useful to test locally.
"""
import subprocess

import click
from huggingface_hub import HfApi, snapshot_download

from lilac.config import read_config
from lilac.db_manager import list_datasets
from lilac.env import env
from lilac.load import load
from lilac.utils import get_datasets_dir, get_hf_dataset_repo_id

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
@click.option(
  '--make_datasets_public',
  help='When true, sets the huggingface datasets uploaded to public. Defaults to false.',
  is_flag=True,
  default=False)
def deploy_demo(config: str, hf_space: str, data_dir: str, overwrite: bool, skip_sync: bool,
                skip_load: bool, skip_build: bool, skip_deploy: bool,
                make_datasets_public: bool) -> None:
  """Deploys the public demo."""
  hf_space_org, hf_space_name = hf_space.split('/')

  if not skip_sync:
    hf_api = HfApi()
    # Get all the datasets uploaded in the org.
    hf_dataset_repos = [dataset.id for dataset in hf_api.list_datasets(author=hf_space_org)]

    for dataset in read_config(config).datasets:
      repo_id = get_hf_dataset_repo_id(hf_space_org, hf_space_name, dataset.namespace, dataset.name)
      if repo_id not in hf_dataset_repos:
        continue

      print(f'Downloading dataset from HuggingFace "{repo_id}": ', dataset)
      snapshot_download(
        repo_id=repo_id,
        repo_type='dataset',
        token=env('HF_ACCESS_TOKEN'),
        local_dir=get_datasets_dir(data_dir),
        ignore_patterns=['.gitattributes', 'README.md'])

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
      data_dir=data_dir,
      make_datasets_public=make_datasets_public,
      # The public demo uses the public pip package.
      use_pip=True,
      # Enable Google Analytics on the public demo.
      disable_google_analytics=False)


def run(cmd: str) -> subprocess.CompletedProcess[bytes]:
  """Run a command and return the result."""
  return subprocess.run(cmd, shell=True, check=True)


if __name__ == '__main__':
  deploy_demo()
