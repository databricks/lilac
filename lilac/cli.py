"""Lilac CLI."""

import click

from . import __version__
from .concepts.db_concept import DISK_CONCEPT_DB
from .load import load_command as load
from .server import start_server


@click.command()
@click.option(
  '--host',
  help='The host address where the web server will listen to.',
  default='127.0.0.1',
  type=str)
@click.option('--port', help='The port number of the web-server', type=int, default=5432)
def start(host: str, port: int) -> None:
  """Starts the Lilac web server."""
  start_server(host=host, port=port, open=True)


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
cli.add_command(load)
cli.add_command(concepts)

if __name__ == '__main__':
  cli()
