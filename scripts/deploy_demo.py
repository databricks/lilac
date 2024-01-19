"""Deploys the public HuggingFace demo to https://huggingface.co/spaces/lilacai/lilac.

This script will, in order:
1) Sync from the HuggingFace space data (only datasets). (--skip_sync to skip syncing)
2) Load the data from the lilac_hf_space.yml config. (--skip_load to skip loading)
3) Push data to the HuggingFace space.

Usage:
poetry run python -m scripts.deploy_demo \
  --project_dir=./demo_data \
  --config=./lilac_hf_space.yml \
  --hf_space=lilacai/lilac

Add:
  --skip_sync to skip syncing data from the HuggingFace space data.
  --skip_load to skip loading the data.
  --load_overwrite to run all data from scratch, overwriting existing data.
  --skip_data_upload to skip uploading data. This will use the datasets already on the space.
  --skip_deploy to skip deploying to HuggingFace. Useful to test locally.

To deploy staging with the same datasets as the public demo:

poetry run python -m scripts.deploy_demo \
  --skip_sync \
  --skip_load \
  --skip_data_upload \
  --hf_space=lilacai/lilac-staging
"""
import subprocess
from typing import Optional

import click
from huggingface_hub import HfApi, snapshot_download
from lilac.config import read_config
from lilac.data.dataset_storage_utils import upload
from lilac.deploy import deploy_project
from lilac.env import env
from lilac.load import load
from lilac.utils import get_datasets_dir, get_hf_dataset_repo_id


@click.command()
@click.option('--config', help='The Lilac config path.', type=str, required=True)
@click.option('--hf_space', help='The huggingface space.', type=str, required=True)
@click.option(
  '--project_dir', help='The local output dir to use to sync the data.', type=str, required=True
)
@click.option(
  '--load_overwrite',
  help='When True, runs all all data from scratch, overwriting existing data. When false, only'
  'load new datasets, embeddings, and signals.',
  type=bool,
  is_flag=True,
  default=False,
)
@click.option(
  '--skip_sync',
  help='Skip syncing data from the HuggingFace space data.',
  type=bool,
  is_flag=True,
  default=False,
)
@click.option('--skip_load', help='Skip loading the data.', type=bool, is_flag=True, default=False)
@click.option(
  '--skip_data_upload',
  help='Skip uploading data. This just uploads the wheel file from the local build.',
  type=bool,
  is_flag=True,
  default=False,
)
@click.option(
  '--deploy_at_head',
  help='Deploy the current working directory, instead of latest PyPI release.',
  type=bool,
  is_flag=True,
  default=False,
)
@click.option(
  '--skip_ts_build',
  help='Skip building the web server TypeScript. '
  'Useful to speed up deploy_at_head if you are only changing python or data.',
  type=bool,
  is_flag=True,
  default=False,
)
@click.option(
  '--skip_deploy',
  help='Skip deploying to HuggingFace. Useful to test locally.',
  type=bool,
  is_flag=True,
  default=False,
)
@click.option(
  '--create_space',
  help='When True, creates the HuggingFace space if it doesnt exist. The space will be created '
  'with small persistent storage.',
  is_flag=True,
  default=False,
)
@click.option(
  '--dataset',
  help="""The dataset(s) to load. If not defined, loads all datasets.
  Specify each dataset as 'namespace/name'""",
  type=str,
  multiple=True,
)
def deploy_demo(
  config: str,
  hf_space: str,
  project_dir: str,
  load_overwrite: bool,
  skip_sync: bool,
  skip_load: bool,
  skip_data_upload: bool,
  deploy_at_head: bool,
  skip_ts_build: bool,
  skip_deploy: bool,
  create_space: bool,
  dataset: Optional[list[str]] = None,
) -> None:
  """Deploys the public demo."""
  # For the public demo, the lilac_hf_space.yml is _always_ uploaded to the HF space
  original_parsed_config = read_config(config)
  # If a dataset is specified, we only sync/load/upload that dataset.
  if dataset is not None:
    config_to_load = original_parsed_config.model_copy()
    config_to_load.datasets = [
      d for d in config_to_load.datasets if f'{d.namespace}/{d.name}' in dataset
    ]
  else:
    config_to_load = original_parsed_config
  hf_space_org, hf_space_name = hf_space.split('/')

  if not skip_sync:
    hf_api = HfApi()
    # Get all the datasets uploaded in the org.
    hf_dataset_repos = [dataset.id for dataset in hf_api.list_datasets(author=hf_space_org)]

    for ds in config_to_load.datasets:
      repo_id = get_hf_dataset_repo_id(hf_space_org, hf_space_name, ds.namespace, ds.name)
      if repo_id not in hf_dataset_repos:
        print('Dataset does not exist on HuggingFace, skipping sync: ', ds)
        continue

      print(f'Downloading dataset from HuggingFace "{repo_id}": ', ds)
      snapshot_download(
        repo_id=repo_id,
        repo_type='dataset',
        token=env('HF_ACCESS_TOKEN'),
        local_dir=get_datasets_dir(project_dir),
        ignore_patterns=['.gitattributes', 'README.md'],
      )

  if not skip_load:
    load(project_dir, config_to_load, load_overwrite)

  ##
  ##  Upload datasets.
  ##
  if not skip_data_upload:
    for ds in config_to_load.datasets:
      repo_id = get_hf_dataset_repo_id(hf_space_org, hf_space_name, ds.namespace, ds.name)
      upload(
        dataset=f'{ds.namespace}/{ds.name}',
        project_dir=project_dir,
        url_or_repo=repo_id,
        # Always make datasets public for demos.
        public=True,
        hf_token=env('HF_ACCESS_TOKEN'),
      )

  if not skip_deploy:
    deploy_project(
      hf_space=hf_space,
      project_config=original_parsed_config,
      project_dir=project_dir,
      # No extra concepts. lilac concepts are pushed by default.
      concepts=[],
      # We only use public concepts in demos.
      skip_concept_upload=True,
      deploy_at_head=deploy_at_head,
      skip_ts_build=skip_ts_build,
      create_space=create_space,
      hf_space_storage='small',
      load_on_space=False,
    )

  # Enable google analytics.
  hf_api = HfApi()
  hf_api.add_space_variable(hf_space, 'GOOGLE_ANALYTICS_ENABLED', 'True')


def run(cmd: str) -> subprocess.CompletedProcess[bytes]:
  """Run a command and return the result."""
  return subprocess.run(cmd, shell=True, check=True)


if __name__ == '__main__':
  deploy_demo()
