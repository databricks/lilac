"""Lilac CLI."""

from os.path import abspath

import click

from . import __version__
from .concepts.db_concept import DISK_CONCEPT_DB
from .env import get_project_dir
from .load import load
from .project import dir_is_project, init, project_dir_from_args
from .server import start_server


@click.command()
@click.argument('project_dir', default='')
@click.option(
  '--host',
  help='The host address where the web server will listen to.',
  default='127.0.0.1',
  type=str)
@click.option('--port', help='The port number of the web-server', type=int, default=5432)
@click.option('--skip_load', help='Skip loading the data.', type=bool, is_flag=True, default=False)
def start(project_dir: str, host: str, port: int, skip_load: bool) -> None:
  """Starts the Lilac web server."""
  project_dir = project_dir_from_args(project_dir)
  if not dir_is_project(project_dir):
    value = str(
      click.prompt(
        f'Lilac will create a project in `{abspath(project_dir)}`. Do you want to continue? (y/n)',
        type=str)).lower()
    if value == 'n':
      exit()

  start_server(host=host, port=port, open=True, project_dir=project_dir, skip_load=skip_load)


@click.command()
@click.argument('project_dir', default='')
def init_command(project_dir: str) -> None:
  """Initialize a Lilac project in a project directory."""
  project_dir = project_dir_from_args(project_dir)
  if not dir_is_project(project_dir):
    value = str(
      click.prompt(
        f'Lilac will create a project in `{abspath(project_dir)}`. Do you want to continue? (y/n)',
        type=str)).lower()
    if value == 'n':
      exit()

  init(project_dir)


@click.command()
@click.argument('project_dir', default='')
@click.option(
  '--config_path',
  type=str,
  help='[Optional] The path to a json or yml file describing the configuration. '
  'The file contents should be an instance of `lilac.Config` or `lilac.DatasetConfig`. '
  'When not defined, uses `LILAC_PROJECT_DIR`/lilac.yml.')
@click.option(
  '--overwrite',
  help='When True, runs all data from scratch, overwriting existing data. When false, only'
  'load new datasets, embeddings, and signals.',
  type=bool,
  is_flag=True,
  default=False)
def load_command(project_dir: str, config_path: str, overwrite: bool) -> None:
  """Load from a project configuration."""
  project_dir = project_dir or get_project_dir()
  if not project_dir:
    raise ValueError(
      '--project_dir or the environment variable `LILAC_PROJECT_DIR` must be defined.')

  load(project_dir, config_path, overwrite)


@click.command()
def version() -> None:
  """Prints the version of Lilac."""
  print(__version__)


@click.command()
def concepts() -> None:
  """Lists lilac concepts."""
  print(DISK_CONCEPT_DB.list())


@click.group()
def cli() -> None:
  """Lilac CLI."""
  pass


cli.add_command(version)

cli.add_command(init_command, name='init')
cli.add_command(load_command, name='load')
cli.add_command(start)

cli.add_command(concepts)

if __name__ == '__main__':
  cli()
