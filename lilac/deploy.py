"""Deploy to a huggingface space.

Usage:
  poetry run lilac deploy-project

"""
import os
import subprocess
import tempfile
from importlib import resources
from typing import TYPE_CHECKING, Any, Literal, Optional, Union

from .concepts.db_concept import DiskConceptDB, get_concept_output_dir
from .config import Config, get_dataset_config
from .env import get_project_dir
from .project import PROJECT_CONFIG_FILENAME, read_project_config, write_project_config
from .sources.huggingface_source import HuggingFaceSource
from .utils import get_dataset_output_dir, get_hf_dataset_repo_id, get_lilac_cache_dir, log, to_yaml

HF_SPACE_DIR = '.hf_spaces'
PY_DIST_DIR = 'dist'
REMOTE_DATA_DIR = 'data'

if TYPE_CHECKING:
  from huggingface_hub import HfApi


def deploy_project(
  hf_space: str,
  project_dir: Optional[str] = None,
  datasets: Optional[list[str]] = None,
  make_datasets_public: Optional[bool] = False,
  concepts: Optional[list[str]] = None,
  skip_cache_upload: Optional[bool] = False,
  skip_data_upload: Optional[bool] = False,
  skip_concept_upload: Optional[bool] = False,
  create_space: Optional[bool] = False,
  load_on_space: Optional[bool] = False,
  hf_space_storage: Optional[Union[Literal['small'], Literal['medium'], Literal['large']]] = None,
  hf_token: Optional[str] = None,
) -> str:
  """Deploy a project to huggingface.

  Args:
    hf_space: The huggingface space. Should be formatted like `SPACE_ORG/SPACE_NAME`.
    project_dir: The project directory to use for the demo. Defaults to `env.LILAC_PROJECT_DIR`.
    datasets: The names of datasets to upload. Defaults to all datasets.
    make_datasets_public: When true, and when --load_on_space is False, sets the HuggingFace
      datasets that reflect local datasets to public. Defaults to false.
    concepts: The names of concepts to upload. Defaults to all concepts.
    skip_cache_upload: Skip uploading the cache files from .cache/lilac which contain cached
      concept pkl models.
    skip_data_upload: When true, kicks the server without uploading data.
    skip_concept_upload: When true, skips uploading concepts.
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

  hf_api = HfApi(token=hf_token)

  operations: list[Union[CommitOperationDelete, CommitOperationAdd]] = deploy_project_operations(
    hf_api=hf_api,
    project_dir=project_dir,
    hf_space=hf_space,
    datasets=datasets,
    make_datasets_public=make_datasets_public,
    concepts=concepts,
    skip_cache_upload=skip_cache_upload,
    skip_data_upload=skip_data_upload,
    skip_concept_upload=skip_concept_upload,
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
  datasets: Optional[list[str]] = None,
  make_datasets_public: Optional[bool] = False,
  concepts: Optional[list[str]] = None,
  skip_cache_upload: Optional[bool] = False,
  skip_data_upload: Optional[bool] = False,
  skip_concept_upload: Optional[bool] = False,
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

  ##
  ##  Create the empty wheel directory. If uploading a local wheel, use scripts.deploy_staging.
  ##
  operations.extend(_make_wheel_dir(hf_api, hf_space))

  ##
  ##  Upload datasets.
  ##
  project_config = read_project_config(project_dir)
  # When datasets aren't explicitly defined, read all datasets and upload them.
  if datasets is None:
    datasets = [f'{d.namespace}/{d.name}' for d in project_config.datasets]

  if not skip_data_upload and not load_on_space:
    lilac_hf_datasets = _upload_datasets(
      api=hf_api,
      project_dir=project_dir,
      hf_space=hf_space,
      datasets=datasets,
      make_datasets_public=make_datasets_public,
    )
  else:
    lilac_hf_datasets = []

  ##
  ##  Upload the HuggingFace application file (README.md) with uploaded datasets so they are synced
  ##  to storage when the docker image boots up.
  ##
  if (lilac_hf_datasets and not skip_data_upload) or load_on_space:
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
          'datasets': [d for d in lilac_hf_datasets],
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
  if datasets and not skip_data_upload:
    project_config_filename = f'data/{PROJECT_CONFIG_FILENAME}'
    # Filter datasets that aren't explicitly defined.
    project_config.datasets = [
      dataset
      for dataset in project_config.datasets
      if f'{dataset.namespace}/{dataset.name}' in datasets
    ]
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

  ##
  ##  Upload the cache files.
  ##
  if not skip_cache_upload:
    operations.extend(_upload_cache(hf_space, project_dir, uploaded_concepts))

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


def _make_wheel_dir(api: Any, hf_space: str) -> list:
  """Creates the wheel directory README. This does not upload local wheels.

  For local wheels, use deploy_local.
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

  # Make an empty readme in py_dist_dir.
  os.makedirs(PY_DIST_DIR, exist_ok=True)
  with open(os.path.join(PY_DIST_DIR, 'README.md'), 'w') as f:
    f.write(
      'This directory is used for locally built whl files.\n'
      'We write a README.md to ensure an empty folder is uploaded when there is no whl.'
    )

  readme_contents = (
    'This directory is used for locally built whl files.\n'
    'We write a README.md to ensure an empty folder is uploaded when there is no whl.'
  ).encode()

  # Remove everything that exists in dist.
  remote_readme_filepath = os.path.join(PY_DIST_DIR, 'README.md')
  if hf_api.file_exists(hf_space, remote_readme_filepath, repo_type='space'):
    operations.append(CommitOperationDelete(path_in_repo=f'{PY_DIST_DIR}/'))

  operations.append(
    # The path in the remote doesn't os.path.join as it is specific to Linux.
    CommitOperationAdd(path_in_repo=f'{PY_DIST_DIR}/README.md', path_or_fileobj=readme_contents)
  )

  return operations


def _upload_cache(hf_space: str, project_dir: str, concepts: Optional[list[str]]) -> list:
  """Adds local cache (model pkl files) to the HuggingFace Space commit."""
  try:
    from huggingface_hub import CommitOperationAdd, CommitOperationDelete, list_files_info
  except ImportError:
    raise ImportError(
      'Could not import the "huggingface_hub" python package. '
      'Please install it with `pip install "huggingface_hub".'
    )

  operations: list[Union[CommitOperationDelete, CommitOperationAdd]] = []

  cache_dir = get_lilac_cache_dir(project_dir)
  cache_files: list[str] = []
  if os.path.exists(cache_dir):
    remote_cache_dir = get_lilac_cache_dir(REMOTE_DATA_DIR)

    files_info = list(list_files_info(hf_space, f'{remote_cache_dir}/', repo_type='space'))
    if files_info:
      operations.append(CommitOperationDelete(path_in_repo=f'{remote_cache_dir}/'))

    for root, _, files in os.walk(cache_dir):
      relative_root = os.path.relpath(root, cache_dir)

      if relative_root.startswith('concept') and files:
        if concepts is None:
          continue
        _, namespace, name = relative_root.split('/', maxsplit=3)
        if f'{namespace}/{name}' not in concepts:
          continue

      for file in files:
        cache_files.append(os.path.join(relative_root, file))
        operations.append(
          CommitOperationAdd(
            # The path in the remote doesn't os.path.join as it is specific to Linux.
            path_in_repo=f'{remote_cache_dir}/{relative_root}/{file}',
            path_or_fileobj=os.path.join(cache_dir, relative_root, file),
          )
        )

  log('Uploading cache files:', cache_files)
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


def _upload_datasets(
  api: Any,
  project_dir: str,
  hf_space: str,
  datasets: list[str],
  make_datasets_public: Optional[bool] = False,
) -> list[str]:
  """Uploads local datasets to HuggingFace datasets."""
  if not make_datasets_public:
    make_datasets_public = False
  try:
    from huggingface_hub import HfApi

  except ImportError:
    raise ImportError(
      'Could not import the "huggingface_hub" python package. '
      'Please install it with `pip install "huggingface_hub".'
    )
  hf_api: HfApi = api

  hf_space_org, hf_space_name = hf_space.split('/')

  log('Uploading datasets: ', datasets)

  lilac_hf_datasets: list[str] = []
  # Upload datasets to HuggingFace. We do this after uploading code to avoid clobbering the data
  # directory.
  # NOTE(nsthorat): This currently doesn't write to persistent storage directly.
  for d in datasets:
    namespace, name = d.split('/')
    dataset_repo_id = get_hf_dataset_repo_id(hf_space_org, hf_space_name, namespace, name)

    print(
      f'Uploading "{d}" to HuggingFace dataset repo '
      f'https://huggingface.co/datasets/{dataset_repo_id}\n'
    )

    hf_api.create_repo(
      dataset_repo_id,
      repo_type='dataset',
      private=not make_datasets_public,
      exist_ok=True,
    )
    dataset_output_dir = get_dataset_output_dir(project_dir, namespace, name)
    hf_api.upload_folder(
      folder_path=dataset_output_dir,
      # The path in the remote doesn't os.path.join as it is specific to Linux.
      path_in_repo=f'{namespace}/{name}',
      repo_id=dataset_repo_id,
      repo_type='dataset',
      # Delete all data on the server.
      delete_patterns='*',
    )

    config = read_project_config(project_dir)
    dataset_config = get_dataset_config(config, namespace, name)
    if dataset_config is None:
      raise ValueError(f'Dataset {namespace}/{name} not found in project config.')

    dataset_link = ''
    if isinstance(dataset_config.source, HuggingFaceSource):
      dataset_link = f'https://huggingface.co/datasets/{dataset_config.source.dataset_name}'

    dataset_config_yaml = to_yaml(
      dataset_config.model_dump(exclude_defaults=True, exclude_none=True, exclude_unset=True)
    )

    readme = (
      'This dataset is generated by [Lilac](http://lilacml.com) for a HuggingFace Space: '
      f'[huggingface.co/spaces/{hf_space_org}/{hf_space_name}]'
      f'(https://huggingface.co/spaces/{hf_space_org}/{hf_space_name}).\n\n'
      + (f'Original dataset: [{dataset_link}]({dataset_link})\n\n' if dataset_link != '' else '')
      + 'Lilac dataset config:\n'
      f'```{dataset_config_yaml}```\n\n'
    ).encode()
    hf_api.upload_file(
      path_or_fileobj=readme,
      path_in_repo='README.md',
      repo_id=dataset_repo_id,
      repo_type='dataset',
    )

    lilac_hf_datasets.append(dataset_repo_id)
  return lilac_hf_datasets


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
