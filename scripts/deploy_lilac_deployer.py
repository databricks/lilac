"""Deploys the Lilac space deployer UI streamlit HuggingFace space.

Usage:
poetry run python -m scripts.deploy_lilac_deployer

Demo: https://huggingface.co/spaces/lilacai/lilac_deployer
"""

import subprocess
from typing import Union

import click
from huggingface_hub import CommitOperationAdd, CommitOperationDelete, HfApi
from lilac.env import env

HF_SPACE_ID = 'lilacai/lilac_deployer'
STREAMLIT_APP_DIR = 'lilac_deployer'


@click.command()
def main() -> None:
  """Deploy the space deployer UI to the HuggingFace space."""
  hf_api = HfApi()
  hf_token = env('HF_ACCESS_TOKEN', False)
  if not hf_token:
    raise ValueError(
      'Please set the `HF_ACCESS_TOKEN` environment flag that has write access '
      f'to the space "{HF_SPACE_ID}"'
    )

  operations: list[Union[CommitOperationDelete, CommitOperationAdd]] = []
  requirements_filepath = f'{STREAMLIT_APP_DIR}/requirements.txt'
  # Write the requirements.txt that will get uploaded.
  run(
    f'poetry export -f requirements.txt --directory={STREAMLIT_APP_DIR} --without-hashes '
    f'--output {requirements_filepath}',
  )

  operations.append(
    CommitOperationAdd(
      path_in_repo='requirements.txt',
      path_or_fileobj=requirements_filepath,
    )
  )
  operations.append(
    CommitOperationAdd(
      path_in_repo='app.py',
      path_or_fileobj=f'{STREAMLIT_APP_DIR}/app.py',
    )
  )
  hf_api.create_commit(
    repo_id=HF_SPACE_ID, repo_type='space', operations=operations, commit_message='Push to HF space'
  )

  print(f'Success! https://huggingface.co/spaces/{HF_SPACE_ID}')


def run(cmd: str) -> subprocess.CompletedProcess[bytes]:
  """Run a command and return the result."""
  return subprocess.run(cmd, shell=True, check=True)


if __name__ == '__main__':
  main()
