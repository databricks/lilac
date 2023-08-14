"""Startup work before running the web server."""

import os
import shutil

from huggingface_hub import scan_cache_dir, snapshot_download

from lilac.concepts.db_concept import CONCEPTS_DIR, DiskConceptDB, get_concept_output_dir
from lilac.db_manager import list_datasets
from lilac.env import data_path, env
from lilac.utils import get_dataset_output_dir, get_lilac_cache_dir, log


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


def main() -> None:
  """Download dataset files from the HF space that was uploaded before building the image."""
  # SPACE_ID is the HuggingFace Space ID environment variable that is automatically set by HF.
  repo_id = env('SPACE_ID', None)
  if not repo_id:
    return

  delete_old_files()
  # Download the huggingface space data. This includes code and datasets, so we move the datasets
  # alone to the data directory.
  snapshot_dir = snapshot_download(repo_id=repo_id, repo_type='space', token=env('HF_ACCESS_TOKEN'))
  # Copy datasets.
  spaces_data_dir = os.path.join(snapshot_dir, 'data')
  datasets = list_datasets(spaces_data_dir)
  for dataset in datasets:
    spaces_dataset_output_dir = get_dataset_output_dir(spaces_data_dir, dataset.namespace,
                                                       dataset.dataset_name)
    persistent_output_dir = get_dataset_output_dir(data_path(), dataset.namespace,
                                                   dataset.dataset_name)
    # Huggingface doesn't let you selectively download files so we just copy the data directory
    # out of the cloned space.
    shutil.rmtree(persistent_output_dir, ignore_errors=True)
    shutil.copytree(spaces_dataset_output_dir, persistent_output_dir)

  # Delete cache files from persistent storage.
  cache_dir = get_lilac_cache_dir(data_path())
  if os.path.exists(cache_dir):
    shutil.rmtree(cache_dir)

  # NOTE: This is temporary during the move of concepts into the pip package. Once all the demos
  # have been updated, this block can be deleted.
  old_lilac_concepts_data_dir = os.path.join(data_path(), CONCEPTS_DIR, 'lilac')
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
    persistent_output_dir = get_concept_output_dir(data_path(), concept.namespace, concept.name)
    shutil.rmtree(persistent_output_dir, ignore_errors=True)
    shutil.copytree(spaces_concept_output_dir, persistent_output_dir, dirs_exist_ok=True)
    shutil.rmtree(spaces_concept_output_dir, ignore_errors=True)


if __name__ == '__main__':
  main()
