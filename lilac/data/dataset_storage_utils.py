"""Utilities for download from a Lilac-processed HuggingFace dataset."""


import os
import shutil
from typing import Optional

from ..config import DatasetConfig, get_dataset_config
from ..db_manager import get_dataset, list_datasets
from ..env import env, get_project_dir
from ..project import add_project_dataset_config, read_project_config
from ..sources.huggingface_source import HuggingFaceSource
from ..utils import (
  get_dataset_output_dir,
  get_datasets_dir,
  get_lilac_cache_dir,
  log,
  read_yaml,
  to_yaml,
)
from .dataset import config_from_dataset
from .dataset_duckdb import DUCKDB_CACHE_FILE


def download(
  url_or_repo: str,
  project_dir: Optional[str] = None,
  dataset_namespace: Optional[str] = 'local',
  dataset_name: Optional[str] = None,
  hf_token: Optional[str] = None,
  overwrite: Optional[bool] = False,
) -> None:
  """Download a Lilac dataset from HuggingFace.

  Args:
    url_or_repo: A remote URL to a Lilac-processed dataset. Currently only supports HuggingFace
      dataset URLs. Can be a full URL: https://huggingface.co/datasets/lilacai/lilac-OpenOrca
      or a repo_id: lilacai/lilac-OpenOrca.
    project_dir: The project directory to use for the demo. Defaults to `env.LILAC_PROJECT_DIR`
      which can be set with `ll.set_project_dir()`.
    dataset_namespace: The local namespace to use. Defaults to 'local'.
    dataset_name: The local dataset name to use. Defaults to the name of the HuggingFace dataset.
    hf_token: The HuggingFace access token to use when making datasets private. This can also be set
      via the `HF_ACCESS_TOKEN` environment flag.
    overwrite: Whether to overwrite the dataset if it already exists.
  """
  try:
    from huggingface_hub import snapshot_download
  except ImportError:
    raise ImportError(
      'Could not import the "huggingface_hub" python package. '
      'Please install it with `pip install "huggingface_hub".'
    )

  repo_id = url_or_repo.removeprefix('https://huggingface.co/datasets/')

  project_dir = project_dir or get_project_dir()
  datasets_dir = get_datasets_dir(project_dir)
  cache_dir = get_lilac_cache_dir(project_dir)
  os.makedirs(datasets_dir, exist_ok=True)

  log(f'Downloading "{repo_id}" from HuggingFace to {datasets_dir}')
  repo_subdir = os.path.join(cache_dir, 'hf_download', repo_id)
  snapshot_download(
    repo_id=repo_id,
    repo_type='dataset',
    token=env('HF_ACCESS_TOKEN', hf_token),
    local_dir=repo_subdir,
    ignore_patterns=['.gitattributes', 'README.md'],
    local_dir_use_symlinks=False,
  )

  # Find the name of the remote namespace and dataset name.
  remote_namespace = [
    d for d in os.listdir(repo_subdir) if os.path.isdir(os.path.join(repo_subdir, d))
  ][0]
  remote_name = os.listdir(os.path.join(repo_subdir, remote_namespace))[0]
  src = os.path.join(repo_subdir, remote_namespace, remote_name)

  dataset_namespace = dataset_namespace or remote_namespace
  dataset_name = dataset_name or remote_name

  # Check the dataset doesn't already exist.
  datasets = list_datasets(project_dir)
  for dataset in datasets:
    if dataset.namespace == dataset_namespace and dataset.dataset_name == dataset_name:
      if not overwrite:
        raise ValueError(
          f'Dataset {dataset_namespace}/{dataset_name} already exists. '
          'Use --overwrite to overwrite it.'
        )
      else:
        log(f'Overwriting existing dataset {dataset_namespace}/{dataset_name}')
        shutil.rmtree(os.path.join(datasets_dir, dataset_namespace, dataset_name))

  dataset_dir = os.path.join(datasets_dir, dataset_namespace, dataset_name)
  os.makedirs(dataset_dir, exist_ok=True)

  shutil.copytree(src, dataset_dir, dirs_exist_ok=True)

  ds = get_dataset(dataset_namespace, dataset_name)
  dataset_config_filename = os.path.join(dataset_dir, 'dataset_config.yml')
  if os.path.exists(dataset_config_filename):
    dataset_config = DatasetConfig(**read_yaml(dataset_config_filename))
  else:
    dataset_config = config_from_dataset(ds)

  add_project_dataset_config(dataset_config, project_dir, overwrite=True)

  log('Wrote dataset to', dataset_dir)


def upload(
  dataset: str,
  project_dir: Optional[str] = None,
  url_or_repo: Optional[str] = None,
  public: Optional[bool] = False,
  readme_suffix: Optional[str] = None,
  hf_token: Optional[str] = None,
) -> None:
  """Uploads local datasets to HuggingFace datasets.

  Args:
    project_dir: The project directory to use for the demo. Defaults to `env.LILAC_PROJECT_DIR`
      which can be set with `ll.set_project_dir()`.
    dataset: The dataset to upload. Can be a local dataset name, or a namespace/dataset name.
    url_or_repo: The HuggingFace dataset repo ID to use. If not specified, will be automatically
      generated.
    public: Whether to make the dataset public. Defaults to False.
    readme_suffix: A suffix to add to the README.md file. Defaults to None.
    hf_token: The HuggingFace access token to use when making datasets private. This can also be set
      via the `HF_ACCESS_TOKEN` environment flag.
  """
  if not public:
    public = False
  project_dir = project_dir or get_project_dir()

  try:
    from huggingface_hub import HfApi

  except ImportError:
    raise ImportError(
      'Could not import the "huggingface_hub" python package. '
      'Please install it with `pip install "huggingface_hub".'
    )
  hf_api = HfApi(token=env('HF_ACCESS_TOKEN', hf_token))

  log('Uploading dataset: ', dataset)

  namespace, name = dataset.split('/')
  if url_or_repo:
    repo_id = url_or_repo.removeprefix('https://huggingface.co/datasets/')
  else:
    repo_id = _dataset_repo_id(dataset)

  dataset_link = f'https://huggingface.co/datasets/{repo_id}'
  log(f'Uploading "{dataset}" to HuggingFace dataset repo ' f'{dataset_link}')

  hf_api.create_repo(
    repo_id,
    repo_type='dataset',
    private=not public,
    exist_ok=True,
  )
  dataset_output_dir = get_dataset_output_dir(project_dir, namespace, name)
  hf_api.upload_folder(
    folder_path=dataset_output_dir,
    # The path in the remote doesn't os.path.join as it is specific to Linux.
    path_in_repo=f'{namespace}/{name}',
    repo_id=repo_id,
    repo_type='dataset',
    # Delete all data on the server.
    delete_patterns='*',
    ignore_patterns=[DUCKDB_CACHE_FILE + '*'],
  )

  config = read_project_config(project_dir)
  dataset_config = get_dataset_config(config, namespace, name)
  if dataset_config is None:
    raise ValueError(f'Dataset {namespace}/{name} not found in project config.')

  original_dataset_link = ''
  if isinstance(dataset_config.source, HuggingFaceSource):
    original_dataset_link = f'https://huggingface.co/datasets/{dataset_config.source.dataset_name}'

  dataset_config_yaml = to_yaml(
    dataset_config.model_dump(exclude_defaults=True, exclude_none=True, exclude_unset=True)
  )
  hf_api.upload_file(
    path_or_fileobj=dataset_config_yaml.encode(),
    path_in_repo='dataset_config.yml',
    repo_id=repo_id,
    repo_type='dataset',
  )

  readme = (
    '---\n'
    'tags:\n'
    '- Lilac\n'
    '---\n'
    f'# {dataset}\n'
    'This dataset is a [Lilac](http://lilacml.com) processed dataset. '
    + (
      f'Original dataset: [{original_dataset_link}]({original_dataset_link})\n\n'
      if original_dataset_link != ''
      else ''
    )
    + 'To download the dataset to a local directory:\n\n'
    '```bash\n'
    f'lilac download {repo_id}\n'
    '```\n\n'
    'or from python with:\n\n'
    '```py\n'
    f'll.download("{url_or_repo}")\n'
    '```\n\n' + (readme_suffix or '')
  ).encode()
  hf_api.upload_file(
    path_or_fileobj=readme,
    path_in_repo='README.md',
    repo_id=repo_id,
    repo_type='dataset',
  )

  log(
    f'\nDataset "{dataset}" uploaded to {dataset_link}\n\n'
    'Download the dataset with: \n\n'
    f'$: lilac download {repo_id}\n\n'
    'or from python with: \n\n'
    '```py\n'
    f'll.download("{url_or_repo}")\n'
    '```'
  )


def _dataset_repo_id(dataset: str) -> str:
  """Returns the dataset repo ID from a dataset."""
  namespace, dataset_name = dataset.split('/')
  return f'lilac-{namespace}-{dataset_name}'
