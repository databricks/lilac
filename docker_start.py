"""Startup work before running the web server."""

import os
import shutil
from typing import TypedDict

import yaml
from huggingface_hub import scan_cache_dir, snapshot_download

from lilac.concepts.db_concept import CONCEPTS_DIR, DiskConceptDB, get_concept_output_dir
from lilac.env import env, get_project_dir
from lilac.project import PROJECT_CONFIG_FILENAME
from lilac.utils import get_datasets_dir, get_lilac_cache_dir, log


def delete_old_files() -> None:
  """Delete old files from the cache."""
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
      [revision.commit_hash for revision in repo.revisions if revision != latest_revision])
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


def main() -> None:
  """Download dataset files from the HF space that was uploaded before building the image."""
  # SPACE_ID is the HuggingFace Space ID environment variable that is automatically set by HF.
  repo_id = env('SPACE_ID', None)
  if not repo_id:
    return

  delete_old_files()

  with open(os.path.abspath('README.md')) as f:
    # Strip the '---' for the huggingface readme config.
    readme = f.read().strip().strip('---')
    hf_config: HfSpaceConfig = yaml.safe_load(readme)

  # Download the huggingface space data. This includes code and datasets, so we move the datasets
  # alone to the data directory.

  datasets_dir = get_datasets_dir(get_project_dir())
  os.makedirs(datasets_dir, exist_ok=True)
  for lilac_hf_dataset in hf_config['datasets']:
    print('Downloading dataset from HuggingFace: ', lilac_hf_dataset)
    snapshot_download(
      repo_id=lilac_hf_dataset,
      repo_type='dataset',
      token=env('HF_ACCESS_TOKEN'),
      local_dir=datasets_dir,
      ignore_patterns=['.gitattributes', 'README.md'])

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

  # NOTE: This is temporary during the move of concepts into the pip package. Once all the demos
  # have been updated, this block can be deleted.
  old_lilac_concepts_data_dir = os.path.join(get_project_dir(), CONCEPTS_DIR, 'lilac')
  if os.path.exists(old_lilac_concepts_data_dir):
    shutil.rmtree(old_lilac_concepts_data_dir)

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
    spaces_concept_output_dir = get_concept_output_dir(spaces_data_dir, concept.namespace,
                                                       concept.name)
    persistent_output_dir = get_concept_output_dir(get_project_dir(), concept.namespace,
                                                   concept.name)
    shutil.rmtree(persistent_output_dir, ignore_errors=True)
    shutil.copytree(spaces_concept_output_dir, persistent_output_dir, dirs_exist_ok=True)
    shutil.rmtree(spaces_concept_output_dir, ignore_errors=True)


if __name__ == '__main__':
  main()
