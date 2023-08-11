"""Deploy to a huggingface space."""
import os
import shutil
import subprocess
from typing import Optional

import click
from huggingface_hub import HfApi

from lilac.concepts.db_concept import DiskConceptDB, get_concept_output_dir
from lilac.env import data_path, env
from lilac.utils import get_dataset_output_dir, get_lilac_cache_dir

HF_SPACE_DIR = '.hf_spaces'


@click.command()
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
  '--data_dir',
  help='The data directory to use for the demo. Defaults to `env.DATA_DIR`.',
  type=str,
  default=data_path())
def deploy_hf_command(hf_username: Optional[str], hf_space: Optional[str], dataset: list[str],
                      concept: list[str], skip_build: bool, skip_cache: bool,
                      data_dir: Optional[str]) -> None:
  """Generate the huggingface space app."""
  deploy_hf(hf_username, hf_space, dataset, concept, skip_build, skip_cache, data_dir)


def deploy_hf(hf_username: Optional[str], hf_space: Optional[str], datasets: list[str],
              concepts: list[str], skip_build: bool, skip_cache: bool,
              data_dir: Optional[str]) -> None:
  """Generate the huggingface space app."""
  data_dir = data_dir or data_path()
  hf_username = hf_username or env('HF_USERNAME')
  if not hf_username:
    raise ValueError('Must specify --hf_username or set env.HF_USERNAME')

  hf_space = hf_space or env('HF_STAGING_DEMO_REPO')
  if not hf_space:
    raise ValueError('Must specify --hf_space or set env.HF_STAGING_DEMO_REPO')

  # Build the web server Svelte & TypeScript.
  if not skip_build:
    run('sh ./scripts/build_server_prod.sh')

  hf_space_dir = os.path.join(data_dir, HF_SPACE_DIR)

  run(f'mkdir -p {hf_space_dir}')

  # Clone the HuggingFace spaces repo.
  repo_basedir = os.path.join(hf_space_dir, hf_space)
  run(f'rm -rf {repo_basedir}')
  run(f'git clone https://{hf_username}@huggingface.co/spaces/{hf_space} {repo_basedir} '
      '--depth 1 --quiet --no-checkout')

  # Clear out the repo.
  run(f'rm -rf {repo_basedir}/*')

  # Export the requirements file so it can be pip installed in the docker container.
  run(f'poetry export --extras all --without-hashes > {repo_basedir}/requirements.txt')

  # Copy source code.
  shutil.copytree('lilac', os.path.join(repo_basedir, 'lilac'), dirs_exist_ok=True)

  # Copy a subset of root files.
  copy_files = ['.dockerignore', '.env', 'Dockerfile', 'LICENSE']
  for copy_file in copy_files:
    shutil.copyfile(copy_file, os.path.join(repo_basedir, copy_file))

  # Create an .env.local to set HF-specific flags.
  with open(f'{repo_basedir}/.env.demo', 'w') as f:
    f.write("""LILAC_DATA_PATH='/data'
HF_HOME='/data/.huggingface'
TRANSFORMERS_CACHE='/data/.cache'
XDG_CACHE_HOME='/data/.cache'
""")

  # Create a .gitignore to avoid uploading unnecessary files.
  with open(f'{repo_basedir}/.gitignore', 'w') as f:
    f.write("""__pycache__/
**/*.pyc
**/*.pyo
**/*.pyd
**/*_test.py
""")

  # Create the huggingface README.
  with open(f'{repo_basedir}/README.md', 'w') as f:
    f.write("""---
title: Lilac
emoji: 🌷
colorFrom: purple
colorTo: purple
sdk: docker
app_port: 5432
---""")

  run(f"""pushd {repo_basedir} > /dev/null && \
      git add . && git add -f lilac/web && \
      (git diff-index --quiet --cached HEAD ||
        (git commit -a -m "Push" --quiet && git push)) && \
      popd > /dev/null""")

  # Upload the cache files.
  hf_api = HfApi()
  if not skip_cache:
    hf_api.upload_folder(
      folder_path=get_lilac_cache_dir(data_dir),
      path_in_repo=get_lilac_cache_dir('data'),
      repo_id=hf_space,
      repo_type='space',
      # Delete all data on the server.
      delete_patterns='*')

  # Upload datasets to HuggingFace. We do this after uploading code to avoid clobbering the data
  # directory.
  # NOTE(nsthorat): This currently doesn't write to persistent storage directly.
  for d in datasets:
    namespace, name = d.split('/')

    hf_api.upload_folder(
      folder_path=get_dataset_output_dir(data_dir, namespace, name),
      path_in_repo=get_dataset_output_dir('data', namespace, name),
      repo_id=hf_space,
      repo_type='space',
      # Delete all data on the server.
      delete_patterns='*')

  disk_concepts = [
    # Remove lilac concepts as they're checked in, and not in the
    f'{c.namespace}/{c.name}' for c in DiskConceptDB(data_dir).list() if c.namespace != 'lilac'
  ]
  for c in concepts:
    if c not in disk_concepts:
      raise ValueError(f'Concept "{c}" not found in disk concepts: {disk_concepts}')

  for c in concepts:
    namespace, name = c.split('/')
    hf_api.upload_folder(
      folder_path=get_concept_output_dir(data_dir, namespace, name),
      path_in_repo=get_concept_output_dir('data', namespace, name),
      repo_id=hf_space,
      repo_type='space',
      # Delete all data on the server.
      delete_patterns='*')


def run(cmd: str) -> subprocess.CompletedProcess[bytes]:
  """Run a command and return the result."""
  return subprocess.run(cmd, shell=True, check=True)


if __name__ == '__main__':
  deploy_hf_command()
