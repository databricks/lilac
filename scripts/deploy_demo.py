"""Deploys the public HuggingFace demo to https://huggingface.co/spaces/lilacai/lilac."""
import os
import shutil
import subprocess

import click

from lilac.concepts.db_concept import CONCEPTS_DIR
from lilac.env import data_path
from lilac.load import load
from lilac.utils import list_datasets

from .deploy_hf import deploy_hf

DEMO_DATA_DIR = 'demo_data'
DEMO_CONFIG_PATH = 'demo.yml'
DEMO_HF_SPACE = 'lilacai/lilac'


@click.command()
@click.option(
  '--overwrite',
  help='When True, runs all all data from scratch, overwriting existing data. When false, only'
  'load new datasets, embeddings, and signals.',
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
def deploy_demo(overwrite: bool, skip_load: bool, skip_build: bool) -> None:
  """Deploys the public demo."""
  if not skip_load:
    load(DEMO_DATA_DIR, DEMO_CONFIG_PATH, overwrite)

  # Copy lilac concepts to the demo data dir from the default data_path: 'data'.
  shutil.copytree(
    os.path.join(data_path(), CONCEPTS_DIR, 'lilac'),
    os.path.join(DEMO_DATA_DIR, CONCEPTS_DIR, 'lilac'),
    dirs_exist_ok=True)

  datasets = [f'{d.namespace}/{d.dataset_name}' for d in list_datasets(DEMO_DATA_DIR)]
  deploy_hf(
    # Take this from the env variable.
    hf_username=None,
    hf_space=DEMO_HF_SPACE,
    datasets=datasets,
    # No extra concepts. lilac concepts are pushed by default.
    concepts=[],
    skip_build=skip_build,
    data_dir=DEMO_DATA_DIR)


def run(cmd: str) -> subprocess.CompletedProcess[bytes]:
  """Run a command and return the result."""
  return subprocess.run(cmd, shell=True, check=True)


if __name__ == '__main__':
  deploy_demo()
