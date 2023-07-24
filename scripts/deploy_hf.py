"""Deploy to a huggingface space."""
import os
import shutil
import subprocess
from typing import Optional

import click
from huggingface_hub import HfApi

from lilac.concepts.db_concept import DiskConceptDB, get_concept_output_dir
from lilac.config import CONFIG, data_path
from lilac.utils import get_dataset_output_dir

HF_SPACE_DIR = os.path.join(data_path(), '.hf_spaces')


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
def main(hf_username: Optional[str], hf_space: Optional[str], dataset: list[str],
         concept: list[str], skip_build: bool) -> None:
  """Generate the huggingface space app."""
  hf_username = hf_username or CONFIG['HF_USERNAME']
  if not hf_username:
    raise ValueError('Must specify --hf_username or set env.HF_USERNAME')

  hf_space = hf_space or CONFIG['HF_STAGING_DEMO_REPO']
  if not hf_space:
    raise ValueError('Must specify --hf_space or set env.HF_STAGING_DEMO_REPO')

  # Build the web server Svelte & TypeScript.
  if not skip_build:
    run('sh ./scripts/build_server_prod.sh')

  run(f'mkdir -p {HF_SPACE_DIR}')

  # Clone the HuggingFace spaces repo.
  repo_basedir = os.path.join(HF_SPACE_DIR, hf_space)
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
HF_DATASETS_CACHE='/data/.cache'
TRANSFORMERS_CACHE='/data/.cache'
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
title: Lilac Blueprint
emoji: 🌷
colorFrom: purple
colorTo: purple
sdk: docker
app_port: 5432
---""")

  run(f"""pushd {repo_basedir} > /dev/null && \
      git add . && git add -f lilac/web && \
      git commit -a -m "Push" --quiet && \
      git push && \
      popd > /dev/null""")

  # Upload datasets to HuggingFace. We do this after uploading code to avoid clobbering the data
  # directory.
  # NOTE(nsthorat): This currently doesn't write to persistent storage directly.
  hf_api = HfApi()
  for d in dataset:
    namespace, name = d.split('/')

    hf_api.upload_folder(
      folder_path=get_dataset_output_dir(data_path(), namespace, name),
      path_in_repo=get_dataset_output_dir('data', namespace, name),
      repo_id=hf_space,
      repo_type='space',
      # Data files might be large, so we upload in chunks.
      multi_commits=True,
      # Delete all data on the server.
      delete_patterns='*')

  disk_concepts = [f'{c.namespace}/{c.name}' for c in DiskConceptDB(data_path()).list()]
  for c in concept:
    if c not in disk_concepts:
      raise ValueError(f'Concept "{c}" not found in disk concepts: {disk_concepts}')

  lilac_concepts = [c for c in disk_concepts if c.startswith('lilac/')]
  concepts = lilac_concepts + list(concept)

  for c in concepts:
    namespace, name = c.split('/')
    hf_api.upload_folder(
      folder_path=get_concept_output_dir(data_path(), namespace, name),
      path_in_repo=get_concept_output_dir('data', namespace, name),
      repo_id=hf_space,
      repo_type='space',
      # Delete all data on the server.
      delete_patterns='*')


def run(cmd: str) -> subprocess.CompletedProcess[bytes]:
  """Run a command and return the result."""
  return subprocess.run(cmd, shell=True, check=True)


if __name__ == '__main__':
  main()
