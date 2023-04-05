"""Tests for the pandas source."""
import pathlib

from ...schema import UUID_COLUMN, Field, Schema
from .huggingface_source import HuggingFaceDataset
from .source import SourceProcessResult


async def test_simple_hf(tmp_path: pathlib.Path) -> None:
  source = HuggingFaceDataset(huggingface_dataset_name='imdb')

  async def shards_loader(shard_infos: list[dict]) -> list[dict]:
    return [source.process_shard(x) for x in shard_infos]

  print(tmp_path, shards_loader)
  result = await source.process(str(tmp_path), shards_loader)
  expected_result = SourceProcessResult(data_schema=Schema(
      fields={
          UUID_COLUMN: Field(dtype='binary'),
          'name': Field(dtype='string'),
          'age': Field(dtype='int64')
      }),
                                        num_items=3,
                                        filepaths=[])

  # Validate except for the filepaths, which are not deterministic.
  expected_result.filepaths = result.filepaths
  assert result == expected_result
  assert len(result.filepaths) == 1
