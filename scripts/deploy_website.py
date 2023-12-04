"""Deploys the website to lilacml.com.

Usage:
poetry run python -m scripts.deploy_website

Add:
  --staging to deploy to the staging environment.
"""

import os
import subprocess

import click


@click.command()
@click.option(
  '--staging',
  is_flag=True,
  help='If true, it deploys to a staging environment.',
  default=False,
  type=bool,
)
def main(staging: bool) -> None:
  """Generate a web client from the OpenAPI spec."""
  run('./scripts/build_docs.sh')
  os.chdir('docs')

  run('firebase login --reauth')
  if staging:
    run('firebase hosting:channel:deploy staging')
  else:
    run('firebase deploy --only hosting')

  os.chdir('..')


def run(cmd: str) -> subprocess.CompletedProcess[bytes]:
  """Run a command and return the result."""
  return subprocess.run(cmd, shell=True, check=True)


if __name__ == '__main__':
  main()
