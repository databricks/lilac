"""Deploy to a huggingface space.

Usage:
  poetry run lilac deploy-project

"""
import os
import shutil
import subprocess
import tempfile
from importlib import resources
from typing import TYPE_CHECKING, Any, Literal, Optional, Union

from .concepts.db_concept import CONCEPTS_DIR, DiskConceptDB, get_concept_output_dir
from .config import Config
from .env import get_project_dir
from .project import PROJECT_CONFIG_FILENAME, read_project_config, write_project_config
from .utils import get_hf_dataset_repo_id, get_lilac_cache_dir, log, to_yaml

HF_SPACE_DIR = '.hf_spaces'
PY_DIST_DIR = 'dist'
REMOTE_DATA_DIR = 'data'

if TYPE_CHECKING:
  from huggingface_hub import HfApi


def deploy_project(
  hf_space: str,
  project_config: Optional[Config] = None,
  project_dir: Optional[str] = None,
  concepts: Optional[list[str]] = None,
  skip_concept_upload: Optional[bool] = False,
  deploy_at_head: bool = False,
  skip_ts_build: bool = False,
  create_space: Optional[bool] = False,
  load_on_space: Optional[bool] = False,
  hf_space_storage: Optional[Union[Literal['small'], Literal['medium'], Literal['large']]] = None,
  hf_token: Optional[str] = None,
) -> str:
  """Deploy a project to huggingface.

  Args:
    hf_space: The huggingface space. Should be formatted like `SPACE_ORG/SPACE_NAME`.
    project_config: A project config for the space; defaults to config file found in project_dir.
    project_dir: The project directory to grab data from. Defaults to `env.LILAC_PROJECT_DIR`.
    concepts: The names of concepts to upload. Defaults to all concepts.
    skip_concept_upload: When true, skips uploading concepts.
    deploy_at_head: If true, deploys the latest code from your machine. Otherwise, deploys from
      PyPI's latest published package.
    skip_ts_build: (Only relevant when deploy_at_head=True) - Skips building frontend assets.
    create_space: When True, creates the HuggingFace space if it doesnt exist. The space will be
      created with the storage type defined by --hf_space_storage.
    load_on_space: When True, loads the datasets from your project in the space and does not upload
      data. NOTE: This could be expensive if your project config locally has embeddings as they will
      be recomputed in HuggingFace.
    hf_space_storage: If defined, sets the HuggingFace space persistent storage type. NOTE: This
      only actually sets the space storage type when creating the space. For more details, see
      https://huggingface.co/docs/hub/spaces-storage
    hf_token: The HuggingFace access token to upload so that the space can access private datasets.
  """
  try:
    from huggingface_hub import CommitOperationAdd, CommitOperationDelete, HfApi
  except ImportError:
    raise ImportError(
      'Could not import the "huggingface_hub" python package. '
      'Please install it with `pip install "huggingface_hub".'
    )

  project_dir = project_dir or get_project_dir()
  if not project_dir:
    raise ValueError(
      '--project_dir or the environment variable `LILAC_PROJECT_DIR` must be defined.'
    )

  project_config = project_config or read_project_config(project_dir)
  hf_api = HfApi(token=hf_token)

  operations: list[Union[CommitOperationDelete, CommitOperationAdd]] = deploy_project_operations(
    hf_api=hf_api,
    project_dir=project_dir,
    hf_space=hf_space,
    project_config=project_config,
    concepts=concepts,
    skip_concept_upload=skip_concept_upload,
    deploy_at_head=deploy_at_head,
    skip_ts_build=skip_ts_build,
    create_space=create_space,
    load_on_space=load_on_space,
    hf_space_storage=hf_space_storage,
  )

  # Atomically commit all the operations so we don't kick the server multiple times.
  hf_api.create_commit(
    repo_id=hf_space,
    repo_type='space',
    operations=operations,
    commit_message='Push to HF space',
  )

  link = f'https://huggingface.co/spaces/{hf_space}'
  log(f'Done! View your space at {link}')
  return link


def deploy_project_operations(
  hf_api: 'HfApi',
  project_dir: str,
  hf_space: str,
  project_config: Config,
  concepts: Optional[list[str]] = None,
  skip_concept_upload: Optional[bool] = False,
  deploy_at_head: bool = False,
  skip_ts_build: bool = False,
  create_space: Optional[bool] = False,
  load_on_space: Optional[bool] = False,
  hf_space_storage: Optional[Union[Literal['small'], Literal['medium'], Literal['large']]] = None,
) -> list:
  """The commit operations for a project deployment."""
  try:
    from huggingface_hub import CommitOperationAdd, CommitOperationDelete
    from huggingface_hub.utils._errors import RepositoryNotFoundError
  except ImportError as e:
    raise ImportError(
      'Could not import the "huggingface_hub" python package. '
      'Please install it with `pip install "huggingface_hub".'
    ) from e

  operations: list[Union[CommitOperationDelete, CommitOperationAdd]] = []

  try:
    repo_info = hf_api.repo_info(hf_space, repo_type='space')
  except RepositoryNotFoundError as e:
    if not create_space:
      raise ValueError(
        'The huggingface space does not exist! '
        'Please pass --create_space if you wish to create it.'
      ) from e
    repo_info = None
  if repo_info is None:
    log(f'Creating huggingface space https://huggingface.co/spaces/{hf_space}')
    log('The space will be created as private. You can change this from the UI.')

    if hf_space_storage:
      hf_api.request_space_storage(repo_id=hf_space, storage=hf_space_storage)

    hf_api.create_repo(
      repo_id=hf_space,
      private=True,
      space_storage=hf_space_storage,
      repo_type='space',
      space_sdk='docker',
    )

    log(f'Created: https://huggingface.co/spaces/{hf_space}')

  repo_runtime = hf_api.get_space_runtime(repo_id=hf_space)

  log('Deploying project:', project_dir)
  log()

  ##
  ##  Copy the root files for the docker image.
  ##
  log('Copying root files...')
  log()
  # Upload the hf_docker directory.
  hf_docker_dir = str(resources.files('lilac').joinpath('hf_docker'))
  for upload_file in os.listdir(hf_docker_dir):
    operations.append(
      CommitOperationAdd(
        path_in_repo=upload_file, path_or_fileobj=str(os.path.join(hf_docker_dir, upload_file))
      )
    )

  operations.extend(
    _make_wheel_dir(hf_api, hf_space, deploy_at_head=deploy_at_head, skip_ts_build=skip_ts_build)
  )

  ##
  ##  Upload the HuggingFace application file (README.md) with uploaded datasets.
  ##
  hf_space_org, hf_space_name = hf_space.split('/')
  dataset_repos = [
    get_hf_dataset_repo_id(hf_space_org, hf_space_name, d.namespace, d.name)
    for d in project_config.datasets
  ]
  readme = (
    '---\n'
    + to_yaml(
      {
        'title': 'Lilac',
        'emoji': '🌷',
        'colorFrom': 'purple',
        'colorTo': 'purple',
        'sdk': 'docker',
        'app_port': 5432,
        'datasets': dataset_repos,
      }
    )
    + '\n---'
  )
  readme_filename = 'README.md'
  if hf_api.file_exists(hf_space, readme_filename, repo_type='space'):
    operations.append(CommitOperationDelete(path_in_repo=readme_filename))

  operations.append(
    CommitOperationAdd(path_in_repo=readme_filename, path_or_fileobj=readme.encode())
  )
  ##
  ##  Upload the lilac.yml project configuration.
  ##
  project_config_filename = f'data/{PROJECT_CONFIG_FILENAME}'
  if hf_api.file_exists(hf_space, project_config_filename, repo_type='space'):
    operations.append(CommitOperationDelete(path_in_repo=project_config_filename))
  operations.append(
    CommitOperationAdd(
      path_in_repo=project_config_filename,
      path_or_fileobj=to_yaml(
        project_config.model_dump(exclude_defaults=True, exclude_none=True, exclude_unset=True)
      ).encode(),
    )
  )

  ##
  ##  Upload concepts.
  ##
  uploaded_concepts: list[str] = []
  if not skip_concept_upload:
    concept_operations, uploaded_concepts = _upload_concepts(hf_space, project_dir, concepts)
    operations.extend(concept_operations)
    operations.extend(_upload_concept_cache(hf_space, project_dir, uploaded_concepts))

  if repo_runtime.storage:
    hf_api.add_space_variable(hf_space, 'LILAC_PROJECT_DIR', '/data')
    hf_api.add_space_variable(hf_space, 'HF_HOME', '/data/.huggingface')
    hf_api.add_space_variable(hf_space, 'XDG_CACHE_HOME', '/data/.cache')
    hf_api.add_space_variable(hf_space, 'TRANSFORMERS_CACHE', '/data/.cache')
  else:
    hf_api.add_space_variable(hf_space, 'LILAC_PROJECT_DIR', './data')
    hf_api.delete_space_variable(hf_space, 'HF_HOME')
    hf_api.delete_space_variable(hf_space, 'XDG_CACHE_HOME')
    hf_api.delete_space_variable(hf_space, 'TRANSFORMERS_CACHE')

  if load_on_space:
    hf_api.add_space_variable(hf_space, 'LILAC_LOAD_ON_START_SERVER', 'true')
  else:
    hf_api.delete_space_variable(hf_space, 'LILAC_LOAD_ON_START_SERVER')

  if hf_api.token:
    hf_api.add_space_secret(hf_space, 'HF_ACCESS_TOKEN', hf_api.token)

  return operations


def _make_wheel_dir(
  api: Any, hf_space: str, deploy_at_head: bool, skip_ts_build: bool = False
) -> list:
  """Makes the wheel directory for the HuggingFace Space commit.

  An empty directory (README only) is used by default; the dockerfile will then fall back to the
  public pip package. When deploy_at_head is True, a wheel with the latest code on your machine is
  built and uploaded.
  """
  try:
    from huggingface_hub import CommitOperationAdd, CommitOperationDelete, HfApi
  except ImportError:
    raise ImportError(
      'Could not import the "huggingface_hub" python package. '
      'Please install it with `pip install "huggingface_hub".'
    )

  hf_api: HfApi = api

  operations: list[Union[CommitOperationDelete, CommitOperationAdd]] = []

  os.makedirs(PY_DIST_DIR, exist_ok=True)

  # Clean the remote dist dir.
  remote_readme_filepath = os.path.join(PY_DIST_DIR, 'README.md')
  if hf_api.file_exists(hf_space, remote_readme_filepath, repo_type='space'):
    operations.append(CommitOperationDelete(path_in_repo=f'{PY_DIST_DIR}/'))

  # Add a file to the dist/ dir so that it's not empty.
  readme_contents = (
    'This directory is used for locally built whl files.\n'
    'We write a README.md to ensure an empty folder is uploaded when there is no whl.'
  ).encode()
  operations.append(
    # The path in the remote doesn't os.path.join as it is specific to Linux.
    CommitOperationAdd(path_in_repo=f'{PY_DIST_DIR}/README.md', path_or_fileobj=readme_contents)
  )

  if deploy_at_head:
    ##
    ##  Build the web server Svelte & TypeScript.
    ##
    if not skip_ts_build:
      log('Building webserver...')
      run('./scripts/build_server_prod.sh')

    # Clean local dist dir before building
    if os.path.exists(PY_DIST_DIR):
      shutil.rmtree(PY_DIST_DIR)
    os.makedirs(PY_DIST_DIR, exist_ok=True)

    # Build the wheel for pip.
    # We have to bump the version number so that Dockerfile sees this wheel as "newer" than PyPI.
    current_lilac_version = run('poetry version -s', capture_output=True).stdout.strip()
    temp_new_version = '1337.0.0'

    run(f'poetry version "{temp_new_version}"')
    run('poetry build -f wheel')
    run(f'poetry version "{current_lilac_version}"')

    # Add wheel files to the commit.
    for upload_file in os.listdir(PY_DIST_DIR):
      operations.append(
        CommitOperationAdd(
          path_in_repo=os.path.join(PY_DIST_DIR, upload_file),
          path_or_fileobj=os.path.join(PY_DIST_DIR, upload_file),
        )
      )
  return operations


def _upload_concept_cache(hf_space: str, project_dir: str, concepts: Optional[list[str]]) -> list:
  """Adds local cache (model pkl files) to the HuggingFace Space commit."""
  try:
    from huggingface_hub import CommitOperationAdd, CommitOperationDelete, list_files_info
  except ImportError:
    raise ImportError(
      'Could not import the "huggingface_hub" python package. '
      'Please install it with `pip install "huggingface_hub".'
    )

  operations: list[Union[CommitOperationDelete, CommitOperationAdd]] = []

  concept_cache_dir = os.path.join(get_lilac_cache_dir(project_dir), CONCEPTS_DIR)
  cache_files: list[str] = []
  remote_cache_dir = os.path.join(get_lilac_cache_dir(REMOTE_DATA_DIR), CONCEPTS_DIR)

  files_info = list(list_files_info(hf_space, f'{remote_cache_dir}/', repo_type='space'))
  if files_info:
    operations.append(CommitOperationDelete(path_in_repo=f'{remote_cache_dir}/'))

  if not os.path.exists(concept_cache_dir):
    return operations
  for root, _, files in os.walk(concept_cache_dir):
    *_, namespace, name = root.rsplit('/', maxsplit=2)
    if concepts and f'{namespace}/{name}' not in concepts:
      continue
    for file in files:
      local_filepath = os.path.join(concept_cache_dir, namespace, name, file)
      # The path in the remote doesn't os.path.join as it is specific to Linux.
      remote_filepath = f'{remote_cache_dir}/{namespace}/{name}/{file}'
      cache_files.append(local_filepath)
      operations.append(
        CommitOperationAdd(
          path_in_repo=remote_filepath,
          path_or_fileobj=local_filepath,
        )
      )

  log('Uploading concept cache files:', cache_files)
  log()

  return operations


def _upload_concepts(
  hf_space: str, project_dir: str, concepts: Optional[list[str]] = None
) -> tuple[list, list[str]]:
  """Adds local concepts to the HuggingFace Space commit."""
  try:
    from huggingface_hub import CommitOperationAdd, CommitOperationDelete, list_files_info
  except ImportError:
    raise ImportError(
      'Could not import the "huggingface_hub" python package. '
      'Please install it with `pip install "huggingface_hub".'
    )

  operations: list[Union[CommitOperationDelete, CommitOperationAdd]] = []

  disk_concepts = [
    # Remove lilac concepts as they're checked in, and not in the
    f'{c.namespace}/{c.name}'
    for c in DiskConceptDB(project_dir).list()
    if c.namespace != 'lilac'
  ]

  # When concepts are not defined, upload all disk concepts.
  if concepts is None:
    concepts = disk_concepts

  for c in concepts:
    if c not in disk_concepts:
      raise ValueError(f'Concept "{c}" not found in disk concepts: {disk_concepts}')

  for c in concepts:
    namespace, name = c.split('/')

    concept_dir = get_concept_output_dir(project_dir, namespace, name)
    remote_concept_dir = get_concept_output_dir(REMOTE_DATA_DIR, namespace, name)

    files_info = list(list_files_info(hf_space, remote_concept_dir, repo_type='space'))
    if files_info:
      operations.append(CommitOperationDelete(path_in_repo=f'{remote_concept_dir}/'))

    for upload_file in os.listdir(concept_dir):
      operations.append(
        CommitOperationAdd(
          # The path in the remote doesn't os.path.join as it is specific to Linux.
          path_in_repo=f'{remote_concept_dir}/{upload_file}',
          path_or_fileobj=os.path.join(concept_dir, upload_file),
        )
      )

  log('Uploading concepts: ', concepts)
  log()
  return operations, concepts


def deploy_config(
  hf_space: str,
  config: Config,
  create_space: Optional[bool] = False,
  hf_space_storage: Optional[Union[Literal['small'], Literal['medium'], Literal['large']]] = None,
  hf_token: Optional[str] = None,
) -> str:
  """Deploys a Lilac config object to a HuggingFace Space.

  Data will be loaded on the HuggingFace space.

  Args:
    hf_space: The HuggingFace space to deploy to. Should be in the format
      "org_name/space_name".
    config: The lilac config object to deploy.
    create_space: When True, creates the HuggingFace space if it doesnt exist. The space will be
      created with the storage type defined by --hf_space_storage.
    hf_space_storage: If defined, sets the HuggingFace space persistent storage type. NOTE: This
      only actually sets the space storage type when creating the space. For more details, see
      https://huggingface.co/docs/hub/spaces-storage
    hf_token: The HuggingFace access token to use when making datasets private. This can also be set
      via the `HF_ACCESS_TOKEN` environment flag.
  """
  with tempfile.TemporaryDirectory() as tmp_project_dir:
    # Write the project config to the temp directory.
    write_project_config(tmp_project_dir, config)

    return deploy_project(
      hf_space=hf_space,
      project_dir=tmp_project_dir,
      create_space=create_space,
      load_on_space=True,
      hf_space_storage=hf_space_storage,
      hf_token=hf_token,
    )


def run(cmd: str, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
  """Run a command and return the result."""
  return subprocess.run(cmd, shell=True, check=True, capture_output=capture_output, text=True)
