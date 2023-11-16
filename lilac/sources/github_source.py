"""Loads files from GitHub using the LlamaIndex GithubRepositoryReader."""
import os
from typing import ClassVar, Iterable, Optional

from pydantic import Field, field_serializer
from typing_extensions import override

from ..schema import Item
from ..source import Source, SourceSchema
from .llama_index_docs_source import LlamaIndexDocsSource

# We currently don't support images or videos, so we filter them out to reduce the load time.
IGNORE_MEDIA_EXTENSIONS = [
  '.png',
  '.jpg',
  '.jpeg',
  '.gif',
  '.mp4',
  '.mov',
  '.avi',
  '.PNG',
  '.JPG',
  '.JPEG',
  '.GIF',
  '.MP4',
  '.MOV',
  '.AVI',
]


class GithubSource(Source):
  """GitHub source code loader

  Loads source code from GitHub repositories using the LlamaIndex GithubRepositoryReader.

  Each file becomes a separate row.

  The following extensions are automatically ignored as Lilac does not yet support media:

  .png, .jpg, .jpeg, .gif, .mp4, .mov, .avi
  """  # noqa: D415, D400

  name: ClassVar[str] = 'github'

  repo: str = Field(description='The GitHub repository to load from. Format: <owner>/<repo>.')
  branch: Optional[str] = Field(
    default='main', description='The branch to load from. Defaults to the main branch.'
  )
  ignore_directories: list[str] = Field(
    description='A list of directories to load from. If not specified, loads from '
    'all directories.'
  )
  ignore_file_extensions: list[str] = Field(description='A list of file extensions to ignore.')
  github_token: Optional[str] = Field(
    default='',
    description='The GitHub token to use for authentication. If not specified, '
    'uses the `GITHUB_TOKEN` environment variable.',
  )

  @field_serializer('github_token')
  def scrub_github_token(self, github_token: str) -> str:
    """Scrubs the github token so it isn't stored on disk."""
    del github_token
    return ''

  _llama_index_docs_source: LlamaIndexDocsSource

  @override
  def setup(self) -> None:
    try:
      from llama_index import GithubRepositoryReader, download_loader
    except ImportError:
      raise ImportError(
        'Could not import dependencies for the "github" source. '
        'Please install with pip install lilac[github]'
      )

    download_loader('GithubRepositoryReader')

    github_token = os.getenv('GITHUB_TOKEN', self.github_token)
    if not github_token:
      raise ValueError(
        'Environment variable `GITHUB_TOKEN` is not set and the github_token arg is not set.'
      )

    owner, repo = self.repo.split('/')

    loader = GithubRepositoryReader(
      owner=owner,
      repo=repo,
      ignore_directories=self.ignore_directories,
      ignore_file_extensions=(self.ignore_file_extensions or []) + IGNORE_MEDIA_EXTENSIONS,
      verbose=True,
      concurrent_requests=10,
      github_token=github_token,
    )

    self._llama_index_docs_source = LlamaIndexDocsSource(loader.load_data(branch=self.branch))
    self._llama_index_docs_source.setup()

  @override
  def source_schema(self) -> SourceSchema:
    """Return the source schema."""
    return self._llama_index_docs_source.source_schema()

  @override
  def yield_items(self) -> Iterable[Item]:
    """Read from GitHub."""
    return self._llama_index_docs_source.yield_items()
