"""Startup work before running the web server on HuggingFace."""

import os
import shutil
from typing import TypedDict

import yaml

from .concepts.db_concept import DiskConceptDB, get_concept_output_dir
from .env import env, get_project_dir
from .project import PROJECT_CONFIG_FILENAME
from .utils import DebugTimer, get_datasets_dir, get_lilac_cache_dir, log


def delete_old_files() -> None:
  """Delete old files from the cache."""
  try:
    from huggingface_hub import scan_cache_dir
  except ImportError:
    raise ImportError(
      'Could not import the "huggingface_hub" python package. '
      'Please install it with `pip install "huggingface_hub".'
    )

  # Scan cache
  try:
    scan = scan_cache_dir()
  except BaseException:
    # Cache was not found.
    return

  # Select revisions to delete
  to_delete = []
  for repo in scan.repos:
    latest_revision = max(repo.revisions, key=lambda x: x.last_modified)
    to_delete.extend(
      [revision.commit_hash for revision in repo.revisions if revision != latest_revision]
    )
  strategy = scan.delete_revisions(*to_delete)

  # Delete them
  log(f'Will delete {len(to_delete)} old revisions and save {strategy.expected_freed_size_str}')
  strategy.execute()


class HfSpaceConfig(TypedDict):
  """The huggingface space config, defined in README.md.

  See:
  https://huggingface.co/docs/hub/spaces-config-reference
  """

  title: str
  datasets: list[str]


def hf_docker_start() -> None:
  """Download dataset files from the HF space that was uploaded before building the image."""
  log('Setting up data dependencies for the server...')
  with DebugTimer('Huggingface docker start'):
    _hf_docker_start()


def _hf_docker_start() -> None:
  try:
    from huggingface_hub import snapshot_download
  except ImportError:
    raise ImportError(
      'Could not import the "huggingface_hub" python package. '
      'Please install it with `pip install "huggingface_hub".'
    )

  # SPACE_ID is the HuggingFace Space ID environment variable that is automatically set by HF.
  repo_id = env('SPACE_ID', None)
  if not repo_id:
    return

  delete_old_files()

  with open(os.path.abspath('README.md')) as f:
    # Strip the '---' for the huggingface readme config.
    readme_contents = f.read()
    dashes = '---'
    first_dashes = readme_contents.find(dashes)
    second_dashes = readme_contents.find(dashes, first_dashes + len(dashes))

    readme = readme_contents[first_dashes + len(dashes) : second_dashes]
    hf_config: HfSpaceConfig = yaml.safe_load(readme)

  # Download the huggingface space data. This includes code and datasets, so we move the datasets
  # alone to the data directory.

  datasets_dir = get_datasets_dir(get_project_dir())
  os.makedirs(datasets_dir, exist_ok=True)
  for lilac_hf_dataset in hf_config.get('datasets', []):
    print('Downloading dataset from HuggingFace: ', lilac_hf_dataset)
    snapshot_download(
      repo_id=lilac_hf_dataset,
      repo_type='dataset',
      token=env('HF_ACCESS_TOKEN'),
      local_dir=datasets_dir,
      ignore_patterns=['.gitattributes', 'README.md'],
    )

  snapshot_dir = snapshot_download(repo_id=repo_id, repo_type='space', token=env('HF_ACCESS_TOKEN'))

  spaces_data_dir = os.path.join(snapshot_dir, 'data')
  # Copy the config file.
  project_config_file = os.path.join(spaces_data_dir, PROJECT_CONFIG_FILENAME)
  if os.path.exists(project_config_file):
    shutil.copy(project_config_file, os.path.join(get_project_dir(), PROJECT_CONFIG_FILENAME))

  # Delete cache files from persistent storage.
  cache_dir = get_lilac_cache_dir(get_project_dir())
  if os.path.exists(cache_dir):
    shutil.rmtree(cache_dir)

  # Copy cache files from the space if they exist.
  spaces_cache_dir = get_lilac_cache_dir(spaces_data_dir)
  if os.path.exists(spaces_cache_dir):
    shutil.copytree(spaces_cache_dir, cache_dir)

  # Copy concepts.
  concepts = DiskConceptDB(spaces_data_dir).list()
  for concept in concepts:
    # Ignore lilac concepts, they're already part of the source code.
    if concept.namespace == 'lilac':
      continue
    spaces_concept_output_dir = get_concept_output_dir(
      spaces_data_dir, concept.namespace, concept.name
    )
    persistent_output_dir = get_concept_output_dir(
      get_project_dir(), concept.namespace, concept.name
    )
    shutil.rmtree(persistent_output_dir, ignore_errors=True)
    shutil.copytree(spaces_concept_output_dir, persistent_output_dir, dirs_exist_ok=True)
    shutil.rmtree(spaces_concept_output_dir, ignore_errors=True)
