"""Deploy to a huggingface space."""
import os
import subprocess

import click
from huggingface_hub import HfApi

HF_SPACE_DIR = 'hf_spaces'


@click.command()
@click.option(
  '--hf_username',
  help='The huggingface username to use to authenticate for the space.',
  type=str,
  required=True)
@click.option(
  '--hf_space',
  help='The huggingface space. Should be formatted like `SPACE_ORG/SPACE_NAME`',
  type=str,
  required=True)
@click.option(
  '--skip_build',
  help='Skip building the web server TypeScript. '
  'Useful if you are only changing python or are only changing data.',
  type=bool,
  default=False)
@click.option('--dataset', help='The name of a dataset to upload', type=str, multiple=True)
def main(hf_username: str, hf_space: str, dataset: list[str], skip_build: bool) -> None:
  """Generate the huggingface space app."""
  # Upload datasets to HuggingFace.
  # NOTE(nsthorat): This currently doesn't write to persistent storage and does not work because of
  # a bug in HuggingFace.
  hf_api = HfApi()
  for d in dataset:
    dataset_path = os.path.join('data', 'datasets', d)
    hf_api.upload_folder(
      folder_path=os.path.abspath(dataset_path),
      path_in_repo='/' + dataset_path,
      repo_id=hf_space,
      repo_type='space',
      # Delete all data on the server.
      delete_patterns='*')

  if not skip_build:
    run('sh ./scripts/build_server_prod.sh')

  run(f'mkdir -p {HF_SPACE_DIR}')

  # Clone the HuggingFace spaces repo.
  repo_basedir = os.path.join(HF_SPACE_DIR, hf_space)
  run(f'rm -rf {repo_basedir}')
  run(f'git clone https://{hf_username}@huggingface.co/spaces/{hf_space} {repo_basedir}')

  run(f'poetry export --without-hashes > {repo_basedir}/requirements.txt')

  # Copy source code.
  copy_dirs = ['src', 'web/blueprint/build']
  for dir in copy_dirs:
    run(f'mkdir -p {repo_basedir}/{dir}')
    run(f'cp -vaR ./{dir}/* {repo_basedir}/{dir}')

  # Copy a subset of root files.
  copy_files = ['.env', 'Dockerfile', 'LICENSE']
  for file in copy_files:
    run(f'cp ./{file} {repo_basedir}/{file}')

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

  # Push to the HuggingFace git repo.
  run(f"""pushd {repo_basedir} && \
      git add . && \
      git commit -a -m "Push" && \
      git push && \
      popd""")


def run(cmd: str) -> subprocess.CompletedProcess[bytes]:
  """Run a command and return the result."""
  return subprocess.run(cmd, shell=True, check=True)


if __name__ == '__main__':
  main()
