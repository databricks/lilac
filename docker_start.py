"""Startup work before running the web server."""

import os
import shutil

from huggingface_hub import snapshot_download

from lilac.concepts.db_concept import CONCEPTS_DIR, DiskConceptDB, get_concept_output_dir
from lilac.db_manager import list_datasets
from lilac.env import data_path, env
from lilac.utils import get_dataset_output_dir, get_lilac_cache_dir


def main() -> None:
  """Download dataset files from the HF space that was uploaded before building the image."""
  # SPACE_ID is the HuggingFace Space ID environment variable that is automatically set by HF.
  repo_id = env('SPACE_ID', None)
  if not repo_id:
    return

  # Download the huggingface space data. This includes code and datasets, so we move the datasets
  # alone to the data directory.
  spaces_download_dir = os.path.join(data_path(), '.hf_spaces', repo_id)
  snapshot_download(
    repo_id=repo_id,
    repo_type='space',
    local_dir=spaces_download_dir,
    local_dir_use_symlinks=False,
    token=env('HF_ACCESS_TOKEN'))
  # Copy datasets.
  spaces_data_dir = os.path.join(spaces_download_dir, 'data')
  datasets = list_datasets(spaces_data_dir)
  for dataset in datasets:
    spaces_dataset_output_dir = get_dataset_output_dir(spaces_data_dir, dataset.namespace,
                                                       dataset.dataset_name)
    persistent_output_dir = get_dataset_output_dir(data_path(), dataset.namespace,
                                                   dataset.dataset_name)
    # Huggingface doesn't let you selectively download files so we just copy the data directory
    # out of the cloned space.
    shutil.rmtree(persistent_output_dir, ignore_errors=True)
    shutil.move(spaces_dataset_output_dir, persistent_output_dir)

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
