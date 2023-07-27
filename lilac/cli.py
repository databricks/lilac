"""Lilac CLI."""

import click

from lilac import __version__
from lilac.server import start_server


@click.command()
@click.option(
  '--host',
  help='The host address where the web server will listen to.',
  default='0.0.0.0',
  type=str)
@click.option('--port', help='The port number of the web-server', type=int, default=5432)
def start(host: str, port: int) -> None:
  """Starts the Lilac web server."""
  start_server(host=host, port=port, open=True)


@click.command()
def version():
  """Prints the version of Lilac."""
  print(__version__)


@click.group()
def cli():
  """Lilac CLI."""
  pass


cli.add_command(start)
cli.add_command(version)

if __name__ == '__main__':
  cli()
