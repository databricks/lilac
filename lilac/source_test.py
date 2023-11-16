"""A source to compute semantic search for a document."""
from typing import ClassVar, Iterable, cast

import pytest
from typing_extensions import override

from .schema import Item
from .source import (
  Source,
  SourceSchema,
  clear_source_registry,
  get_source_cls,
  register_source,
  resolve_source,
)


class TestSource(Source):
  """A test source."""

  name: ClassVar[str] = 'test_source'

  @override
  def setup(self) -> None:
    pass

  @override
  def source_schema(self) -> SourceSchema:
    """Return the source schema."""
    return cast(SourceSchema, None)

  @override
  def yield_items(self) -> Iterable[Item]:
    yield None


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
  assert resolve_source(test_source.model_dump()) == test_source
