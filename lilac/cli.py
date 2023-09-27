"""Lilac CLI."""

from os.path import abspath

import click

from . import __version__
from .concepts.db_concept import DISK_CONCEPT_DB
from .env import get_project_dir
from .hf_docker_start import hf_docker_start
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
@click.option(
  '--load',
  help='Load from the project config upon bootup.',
  type=bool,
  is_flag=True,
  default=False)
def start(project_dir: str, host: str, port: int, load: bool) -> None:
  """Starts the Lilac web server."""
  project_dir = project_dir_from_args(project_dir)
  if not dir_is_project(project_dir):
    value = str(
      click.prompt(
        f'Lilac will create a project in `{abspath(project_dir)}`. Do you want to continue? (y/n)',
        type=str)).lower()
    if value == 'n':
      exit()

  start_server(host=host, port=port, open=True, project_dir=project_dir, load=load)


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
def hf_docker_start_command() -> None:
  """Prepares the binary by downloading datasets for the HuggingFace docker image."""
  hf_docker_start()


@click.command()
@click.option(
  '--project_dir',
  help='The project directory to use for the demo. Defaults to `env.LILAC_PROJECT_DIR`.',
  type=str,
  required=True)
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
  '--make_datasets_public',
  help='When true, sets the huggingface datasets uploaded to public. Defaults to false.',
  is_flag=True,
  default=False)
@click.option(
  '--skip_data_upload',
  help='When true, only uploads the wheel files without any other changes.',
  is_flag=True,
  default=False)
@click.option(
  '--use_pip',
  help='When true, uses the public pip package. When false, builds and uses a local wheel.',
  is_flag=True,
  default=False)
def deploy_hf_command(project_dir: str, hf_username: Optional[str], hf_space: Optional[str],
                      dataset: list[str], concept: list[str], skip_build: bool, skip_cache: bool,
                      make_datasets_public: bool, skip_data_upload: bool, use_pip: bool) -> None:
  """Generate the huggingface space app."""
  deploy_hf(
    project_dir=project_dir,
    hf_username=hf_username,
    hf_space=hf_space,
    datasets=dataset,
    concepts=concept,
    skip_build=skip_build,
    skip_cache=skip_cache,
    make_datasets_public=make_datasets_public,
    skip_data_upload=skip_data_upload,
    use_pip=use_pip)


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

cli.add_command(deploy_hf_command, name='deploy_hf')
cli.add_command(hf_docker_start_command, name='hf_docker_start')

cli.add_command(concepts)

if __name__ == '__main__':
  cli()
