"""Lilac CLI."""

import click

from . import __version__
from .concepts.db_concept import DISK_CONCEPT_DB
from .load import load_command as load
from .project import dir_is_project, project_path_from_args
from .server import start_server


@click.command()
@click.argument('project_path', default='')
@click.option(
  '--host',
  help='The host address where the web server will listen to.',
  default='127.0.0.1',
  type=str)
@click.option('--port', help='The port number of the web-server', type=int, default=5432)
@click.option('--skip_load', help='Skip loading the data.', type=bool, is_flag=True, default=False)
def start(project_path: str, host: str, port: int, skip_load: bool) -> None:
  """Starts the Lilac web server."""
  project_path = project_path_from_args(project_path)
  if not dir_is_project(project_path):
    value = str(
      click.prompt(
        f'Lilac will create a project in `{project_path}`. Do you want to continue? (y/n)',
        type=str)).lower()
    if value == 'n':
      exit()

  start_server(host=host, port=port, open=True, project_path=project_path, skip_load=skip_load)


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


cli.add_command(start)
cli.add_command(version)
cli.add_command(load, name='load')
cli.add_command(concepts)

if __name__ == '__main__':
  cli()
