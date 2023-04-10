"""A source to compute semantic search for a document."""
from typing import Iterable, Optional, cast

import pytest
from pydantic import BaseModel
from typing_extensions import override

from ...tasks import TaskId
from .source import ShardsLoader, Source, SourceProcessResult, SourceShardOut
from .source_registry import clear_source_registry, get_source_cls, register_source, resolve_source


class TestSource(Source[BaseModel]):
  """A test source."""
  name = 'test_source'

  @override
  async def process(self,
                    output_dir: str,
                    shards_loader: Optional[ShardsLoader] = None,
                    task_id: Optional[TaskId] = None) -> SourceProcessResult:
    return cast(SourceProcessResult, None)

  @override
  def process_shard(self, shard_info: BaseModel) -> SourceShardOut:
    return cast(SourceShardOut, None)


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  # Setup.
  register_source(TestSource)

  # Unit test runs.
  yield

  # Teardown.
  clear_source_registry()


def test_get_source_cls() -> None:
  """Test getting a source."""
  assert TestSource == get_source_cls('test_source')


def test_resolve_source() -> None:
  """Test resolving a source."""
  test_source = TestSource()

  # sources pass through.
  assert resolve_source(test_source) == test_source

  # Dicts resolve to the base class.
  assert resolve_source(test_source.dict()) == test_source
