"""Deploy to a huggingface space.

Usage:
  poetry run python -m scripts.deploy_hf*

"""
import os
import shutil
import subprocess
from importlib import resources
from typing import Any, Optional, Union

import click
import yaml

from lilac.concepts.db_concept import DiskConceptDB, get_concept_output_dir
from lilac.config import Config, get_dataset_config
from lilac.env import env, get_project_dir
from lilac.project import PROJECT_CONFIG_FILENAME, read_project_config
from lilac.sources.huggingface_source import HuggingFaceSource
from lilac.utils import get_dataset_output_dir, get_hf_dataset_repo_id, get_lilac_cache_dir, to_yaml

HF_SPACE_DIR = '.hf_spaces'
PY_DIST_DIR = 'dist'


@click.command()
@click.option(
  '--project_dir',
  help='The project directory to use for the demo. Defaults to `env.LILAC_PROJECT_DIR`.',
  type=str,
  required=True)
@click.option(
  '--hf_username', help='The huggingface username to use to authenticate for the space.', type=str)
@click.option(
  '--hf_space',
  help='The huggingface space. Defaults to env.HF_STAGING_DEMO_REPO. '
  'Should be formatted like `SPACE_ORG/SPACE_NAME`.',
  type=str)
@click.option('--dataset', help='The name of a dataset to upload', type=str, multiple=True)
@click.option(
  '--concept',
  help='The name of a concept to upload. By default all lilac/ concepts are uploaded.',
  type=str,
  multiple=True)
@click.option(
  '--skip_build',
  help='Skip building the web server TypeScript. '
  'Useful to speed up the build if you are only changing python or data.',
  type=bool,
  is_flag=True,
  default=False)
@click.option(
  '--skip_cache',
  help='Skip uploading the cache files from .cache/lilac which contain cached concept pkl models.',
  type=bool,
  is_flag=True,
  default=False)
@click.option(
  '--make_datasets_public',
  help='When true, sets the huggingface datasets uploaded to public. Defaults to false.',
  is_flag=True,
  default=False)
@click.option(
  '--skip_data_upload',
  help='When true, only uploads the wheel files without any other changes.',
  is_flag=True,
  default=False)
@click.option(
  '--use_pip',
  help='When true, uses the public pip package. When false, builds and uses a local wheel.',
  is_flag=True,
  default=False)
def deploy_hf_command(project_dir: str, hf_username: Optional[str], hf_space: Optional[str],
                      dataset: list[str], concept: list[str], skip_build: bool, skip_cache: bool,
                      make_datasets_public: bool, skip_data_upload: bool, use_pip: bool) -> None:
  """Generate the huggingface space app."""
  deploy_hf(
    project_dir=project_dir,
    hf_username=hf_username,
    hf_space=hf_space,
    datasets=dataset,
    concepts=concept,
    skip_build=skip_build,
    skip_cache=skip_cache,
    make_datasets_public=make_datasets_public,
    skip_data_upload=skip_data_upload,
    use_pip=use_pip)


def deploy_hf(project_dir: Optional[str], hf_username: Optional[str], hf_space: Optional[str],
              datasets: list[str], concepts: list[str], skip_build: bool, skip_cache: bool,
              make_datasets_public: bool, skip_data_upload: bool, use_pip: bool) -> None:
  """Generate the huggingface space app."""
  try:
    from huggingface_hub import CommitOperationAdd, CommitOperationDelete, HfApi
  except ImportError:
    raise ImportError('Could not import the "huggingface_hub" python package. '
                      'Please install it with `pip install "huggingface_hub".')

  hf_username = hf_username or env('HF_USERNAME')
  if not hf_username:
    raise ValueError('Must specify --hf_username or set env.HF_USERNAME')

  hf_space = hf_space or env('HF_STAGING_DEMO_REPO')
  if not hf_space:
    raise ValueError('Must specify --hf_space or set env.HF_STAGING_DEMO_REPO')

  # Build the web server Svelte & TypeScript.
  if not use_pip and not skip_build:
    print('Building webserver...')
    run('./scripts/build_server_prod.sh')

  operations: list[Union[CommitOperationDelete, CommitOperationAdd]] = []

  hf_api = HfApi()

  print('Copying root files...')
  # Upload the hf_docker directory.
  hf_docker_dir = str(resources.files('lilac').joinpath('hf_docker'))
  for upload_file in os.listdir(hf_docker_dir):
    operations.append(
      CommitOperationAdd(
        path_in_repo=upload_file, path_or_fileobj=str(os.path.join(hf_docker_dir, upload_file))))

  # Unconditionally remove dist. dist is unconditionally uploaded so it is empty when using
  # the public package.
  if os.path.exists(PY_DIST_DIR):
    shutil.rmtree(PY_DIST_DIR)
  os.makedirs(PY_DIST_DIR, exist_ok=True)

  # Make an empty readme in py_dist_dir.
  with open(os.path.join(PY_DIST_DIR, 'README.md'), 'w') as f:
    f.write('This directory is used for locally built whl files.\n'
            'We write a README.md to ensure an empty folder is uploaded when there is no whl.')

  # Build the wheel for pip.
  if not use_pip:
    # We have to change the version to a dev version so that the huggingface demo does not try to
    # install the public pip package.
    current_lilac_version = run('poetry version -s', capture_output=True).stdout.strip()
    # Bump the version temporarily so that the install uses this pip.
    version_parts = current_lilac_version.split('.')
    version_parts[-1] = str(int(version_parts[-1]) + 1)
    temp_new_version = '.'.join(version_parts)

    run(f'poetry version "{temp_new_version}"')
    run('poetry build -f wheel')
    run(f'poetry version "{current_lilac_version}"')

  print('Uploading wheel files...')
  operations.append(CommitOperationDelete(path_in_repo=f'{PY_DIST_DIR}/'))
  for upload_file in os.listdir(PY_DIST_DIR):
    operations.append(
      CommitOperationAdd(
        path_in_repo=os.path.join(PY_DIST_DIR, upload_file),
        path_or_fileobj=os.path.join(PY_DIST_DIR, upload_file)))

  project_dir = project_dir or get_project_dir()
  if not project_dir:
    raise ValueError(
      '--project_dir or the environment variable `LILAC_PROJECT_DIR` must be defined.')

  if not skip_data_upload:
    lilac_hf_datasets = _upload_datasets(
      api=hf_api,
      project_dir=project_dir,
      hf_space=hf_space,
      datasets=datasets,
      make_datasets_public=make_datasets_public)
  else:
    lilac_hf_datasets = []

  # When we've uploaded datasets, set the readme so they are synced on bootup.
  if lilac_hf_datasets:
    readme = '---\n' + to_yaml({
      'title': 'Lilac',
      'emoji': '🌷',
      'colorFrom': 'purple',
      'colorTo': 'purple',
      'sdk': 'docker',
      'app_port': 5432,
      'datasets': [d for d in lilac_hf_datasets],
    }) + '\n---'
    readme_filename = 'README.md'
    operations.append(CommitOperationDelete(path_in_repo=readme_filename))
    operations.append(
      CommitOperationAdd(path_in_repo=readme_filename, path_or_fileobj=readme.encode()))

  # Upload the lilac.yml and filter out any datasets that aren't explicitly defined.
  if datasets:
    project_config_filename = f'data/{PROJECT_CONFIG_FILENAME}'
    project_config = read_project_config(project_dir)
    project_config.datasets = [
      dataset for dataset in project_config.datasets
      if f'{dataset.namespace}/{dataset.name}' in datasets
    ]
    operations.append(CommitOperationDelete(path_in_repo=project_config_filename))
    operations.append(
      CommitOperationAdd(
        path_in_repo=project_config_filename,
        path_or_fileobj=to_yaml(project_config.model_dump()).encode()))

  print('Uploading cache files...')
  # Upload the cache files.
  cache_dir = get_lilac_cache_dir(project_dir)
  if not skip_cache and os.path.exists(cache_dir):
    remote_cache_dir = get_lilac_cache_dir('data')
    operations.append(CommitOperationDelete(path_in_repo=f'{remote_cache_dir}/'))

    for root, _, files in os.walk(cache_dir):
      relative_root = os.path.relpath(root, cache_dir)
      for file in files:
        operations.append(
          CommitOperationAdd(
            path_in_repo=os.path.join(remote_cache_dir, relative_root, file),
            path_or_fileobj=os.path.join(cache_dir, relative_root, file)))

  # Upload concepts.
  print('Uploading concepts...')
  disk_concepts = [
    # Remove lilac concepts as they're checked in, and not in the
    f'{c.namespace}/{c.name}' for c in DiskConceptDB(project_dir).list() if c.namespace != 'lilac'
  ]
  for c in concepts:
    if c not in disk_concepts:
      raise ValueError(f'Concept "{c}" not found in disk concepts: {disk_concepts}')

  for c in concepts:
    namespace, name = c.split('/')

    concept_dir = get_concept_output_dir(project_dir, namespace, name)
    remote_concept_dir = get_concept_output_dir('data', namespace, name)
    operations.append(CommitOperationDelete(path_in_repo=f'{remote_concept_dir}/'))

    for upload_file in os.listdir(concept_dir):
      operations.append(
        CommitOperationAdd(
          path_in_repo=os.path.join(remote_concept_dir, upload_file),
          path_or_fileobj=os.path.join(cache_dir, upload_file)))

  # Atomically commit all the operations so we don't kick the server multiple times.
  hf_api.create_commit(
    repo_id=hf_space,
    repo_type='space',
    operations=operations,
    commit_message='Push to HF space',
  )


def _upload_datasets(api: Any, project_dir: str, hf_space: str, datasets: list[str],
                     make_datasets_public: bool) -> list[str]:
  """Uploads local datasets to HuggingFace datasets."""
  lilac_hf_datasets: list[str] = []

  try:
    from huggingface_hub import HfApi

  except ImportError:
    raise ImportError('Could not import the "huggingface_hub" python package. '
                      'Please install it with `pip install "huggingface_hub".')
  hf_api: HfApi = api

  hf_space_org, hf_space_name = hf_space.split('/')

  # Upload datasets to HuggingFace. We do this after uploading code to avoid clobbering the data
  # directory.
  # NOTE(nsthorat): This currently doesn't write to persistent storage directly.
  for d in datasets:
    namespace, name = d.split('/')
    dataset_repo_id = get_hf_dataset_repo_id(hf_space_org, hf_space_name, namespace, name)

    print(f'Uploading to HuggingFace repo https://huggingface.co/datasets/{dataset_repo_id}\n')

    hf_api.create_repo(
      dataset_repo_id, repo_type='dataset', private=not make_datasets_public, exist_ok=True)
    dataset_output_dir = get_dataset_output_dir(project_dir, namespace, name)
    hf_api.upload_folder(
      folder_path=dataset_output_dir,
      path_in_repo=os.path.join(namespace, name),
      repo_id=dataset_repo_id,
      repo_type='dataset',
      # Delete all data on the server.
      delete_patterns='*')

    config_filepath = os.path.join(project_dir, PROJECT_CONFIG_FILENAME)
    with open(config_filepath) as f:
      config = Config.model_validate(yaml.safe_load(f.read()))

    dataset_link = ''
    dataset_config = get_dataset_config(config, namespace, name)
    if not dataset_config:
      raise ValueError(f'Dataset {namespace}/{name} not found in config.')
    if isinstance(dataset_config.source, HuggingFaceSource):
      dataset_link = f'https://huggingface.co/datasets/{dataset_config.source.dataset_name}'

    dataset_config_dict = dataset_config.model_dump(exclude_none=True, exclude_unset=True)
    readme = (
      ('This dataset is generated by [Lilac](http://lilacml.com) for a HuggingFace Space: '
       f'[huggingface.co/spaces/{hf_space_org}/{hf_space_name}]'
       f'(https://huggingface.co/spaces/{hf_space_org}/{hf_space_name}).\n\n' +
       (f'Original dataset: [{dataset_link}]({dataset_link})\n\n' if dataset_link != '' else '') +
       'Lilac dataset config:\n'
       f'```{dataset_config_dict}```\n\n').encode())
    hf_api.upload_file(
      path_or_fileobj=readme,
      path_in_repo='README.md',
      repo_id=dataset_repo_id,
      repo_type='dataset',
    )

    lilac_hf_datasets.append(dataset_repo_id)
  return lilac_hf_datasets


def run(cmd: str, capture_output=False) -> subprocess.CompletedProcess[str]:
  """Run a command and return the result."""
  return subprocess.run(cmd, shell=True, check=True, capture_output=capture_output, text=True)


if __name__ == '__main__':
  deploy_hf_command()
