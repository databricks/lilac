"""Deploys the website to lilacml.com.

Usage:
poetry run python -m scripts.deploy_website

Add:
  --staging to deploy to the staging environment.
"""

import os
import subprocess

import click

from lilac.env import env


@click.command()
@click.option(
  '--staging',
  is_flag=True,
  help='If true, it deploys to a staging environment.',
  default=False,
  type=bool)
def main(staging: bool) -> None:
  """Generate a web client from the OpenAPI spec."""
  firebase_token = env('FIREBASE_TOKEN')
  if not firebase_token:
    raise ValueError('Missing `FIREBASE_TOKEN` environment variable. Add it to .env.local')

  run('./scripts/build_docs.sh')

  os.chdir('docs')
  if staging:
    run(f'firebase hosting:channel:deploy staging --token "{firebase_token}"')
  else:
    run(f'firebase deploy --only hosting --token "{firebase_token}"')
  os.chdir('..')


def run(cmd: str) -> subprocess.CompletedProcess[bytes]:
  """Run a command and return the result."""
  return subprocess.run(cmd, shell=True, check=True)


if __name__ == '__main__':
  main()
