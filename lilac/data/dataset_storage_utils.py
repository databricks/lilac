"""Utilities for download from a Lilac-processed HuggingFace dataset."""


import os
import shutil
from typing import Optional

from ..config import DatasetConfig
from ..db_manager import get_dataset
from ..env import env, get_project_dir
from ..project import add_project_dataset_config
from ..utils import get_datasets_dir, get_lilac_cache_dir, read_yaml
from .dataset import config_from_dataset


def download(
  url_or_repo: str,
  project_dir: Optional[str] = None,
  dataset_namespace: Optional[str] = 'local',
  dataset_name: Optional[str] = None,
  hf_token: Optional[str] = None,
) -> None:
  """Download a Lilac dataset from HuggingFace.

  Args:
    url_or_repo: A remote URL to a Lilac-processed dataset. Currently only supports HuggingFace
      dataset URLs. Can be a full URL: https://huggingface.co/datasets/lilacai/lilac-OpenOrca-100k
      or a repo_id: lilacai/lilac-OpenOrca-100k.
    project_dir: The project directory to use for the demo. Defaults to `env.LILAC_PROJECT_DIR`
      which can be set with `ll.set_project_dir()`.
    dataset_namespace: The local namespace to use. Defaults to 'local'.
    dataset_name: The local dataset name to use. Defaults to the name of the HuggingFace dataset.
    hf_token: The HuggingFace access token to use when making datasets private. This can also be set
      via the `HF_ACCESS_TOKEN` environment flag.
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

  print(f'Downloading "{repo_id}" from HuggingFace to {datasets_dir}')
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

  print('Wrote dataset to', dataset_dir)
