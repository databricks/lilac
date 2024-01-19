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

from typing import Optional

import click
from lilac.data.dataset_storage_utils import upload
from lilac.deploy import deploy_project
from lilac.env import env
from lilac.project import read_project_config
from lilac.utils import get_hf_dataset_repo_id


@click.command()
@click.option(
  '--hf_space',
  help='The huggingface space. Defaults to env.HF_STAGING_DEMO_REPO. '
  'Should be formatted like `SPACE_ORG/SPACE_NAME`.',
  type=str,
)
@click.option('--dataset', help='The name of a dataset to upload', type=str, multiple=True)
@click.option(
  '--concept',
  help='The name of a concept to upload. By default all lilac/ concepts are uploaded.',
  type=str,
  multiple=True,
)
@click.option(
  '--skip_ts_build',
  help='Skip building the web server TypeScript. '
  'Useful to speed up the build if you are only changing python or data.',
  type=bool,
  is_flag=True,
  default=False,
)
@click.option(
  '--create_space',
  help='When True, creates the HuggingFace space if it doesnt exist. The space will be created '
  'with the storage type defined by --hf_space_storage.',
  is_flag=True,
  default=False,
)
@click.option(
  '--skip_concept_upload',
  help='Skip uploading custom concepts.',
  type=bool,
  is_flag=True,
  default=False,
)
def deploy_staging(
  hf_space: Optional[str] = None,
  dataset: Optional[list[str]] = None,
  concept: Optional[list[str]] = None,
  skip_ts_build: bool = False,
  skip_concept_upload: Optional[bool] = False,
  create_space: Optional[bool] = False,
) -> None:
  """Generate the huggingface space app."""
  # For local deployments, we hard-code the project_dir dir.
  project_dir = 'data'
  hf_space = hf_space or env('HF_STAGING_DEMO_REPO')
  if not hf_space:
    raise ValueError('Must specify --hf_space or set env.HF_STAGING_DEMO_REPO')

  hf_token = env('HF_ACCESS_TOKEN')

  # When datasets are not defined, don't upload any datasets.
  if dataset is None:
    dataset = []
  # When concepts are not defined, don't upload any concepts.
  if concept is None:
    concept = []

  ##
  ##  Upload datasets.
  ##
  for d in dataset:
    upload(
      dataset=d,
      project_dir=project_dir,
      url_or_repo=get_hf_dataset_repo_id(*hf_space.split('/'), *d.split('/')),
      public=False,
      hf_token=hf_token,
    )

  # For staging deployments, we strip down the project config to only the specified datasets
  project_config = read_project_config(project_dir)
  project_config.datasets = [
    d for d in project_config.datasets if f'{d.namespace}/{d.name}' in dataset
  ]
  deploy_project(
    hf_space,
    project_config=project_config,
    project_dir=project_dir,
    concepts=concept,
    skip_concept_upload=skip_concept_upload,
    deploy_at_head=True,
    skip_ts_build=skip_ts_build,
    hf_space_storage=None,
    create_space=create_space,
    hf_token=hf_token,
  )


if __name__ == '__main__':
  deploy_staging()
