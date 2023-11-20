"""Utilities for unit tests."""
import pathlib
import uuid
from datetime import datetime
from typing import Type, cast

import pyarrow.parquet as pq
from pydantic import BaseModel

from .schema import ROWID, Item
from .source import SourceManifest

TEST_TIME = datetime(2023, 8, 15, 1, 23, 45)


def retrieve_parquet_rows(
  tmp_path: pathlib.Path, manifest: SourceManifest, retain_rowid: bool = False
) -> list[Item]:
  """Retrieve the rows from a parquet source."""
  items = []
  for file in manifest.files:
    items.extend(pq.read_table(tmp_path / file).to_pylist())
  for item in items:
    assert ROWID in item
    if not retain_rowid:
      del item[ROWID]
  return items


def allow_any_datetime(cls: Type[BaseModel]) -> None:
  """Overrides the __eq__ method for a pydantic model to allow any datetimes to be equal."""

  # freeze_time and Dask don't play well together so we override equality here.
  def _replace_datetimes(self: dict) -> None:
    # Recursively replace datetimes in both self and other with TEST_TIME.
    for key in self:
      if isinstance(self[key], dict):
        _replace_datetimes(self[key])
      elif isinstance(self[key], datetime):
        self[key] = TEST_TIME

  def _new_eq(self: BaseModel, other: object) -> bool:
    self_dict = self.model_dump()
    other_dict = cast(BaseModel, other).model_dump()
    _replace_datetimes(self_dict)
    return self_dict == other_dict

  cls.__eq__ = _new_eq  # type: ignore


def fake_uuid(id: bytes) -> uuid.UUID:
  """Create a test UUID."""
  return uuid.UUID((id * 16).hex())
