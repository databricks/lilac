"""Utilities for unit tests."""
import os
import pathlib
import uuid
from datetime import datetime
from typing import Type, Union, cast

import pyarrow.parquet as pq
from pydantic import BaseModel

from .schema import ROWID, DataType, Field, Item, Schema, schema_to_arrow_schema

TEST_TIME = datetime(2023, 8, 15, 1, 23, 45)


def read_items(
  data_dir: Union[str, pathlib.Path], filepaths: list[str], schema: Schema
) -> list[Item]:
  """Read the source items from a dataset output directory."""
  items: list[Item] = []
  schema.fields[ROWID] = Field(dtype=DataType.STRING)
  for filepath in filepaths:
    items.extend(
      pq.read_table(
        os.path.join(data_dir, filepath), schema=schema_to_arrow_schema(schema)
      ).to_pylist()
    )
  return items


def allow_any_datetime(cls: Type[BaseModel]) -> None:
  """Overrides the __eq__ method for a pydantic model to allow any datetimes to be equal."""

  # freeze_time and Dask don't play well together so we override equality here.
  def _replace_datetimes(self: dict, other: dict) -> None:
    # Recursively replace datetimes in both self and other with TEST_TIME.
    for key in self:
      if isinstance(self[key], dict):
        _replace_datetimes(self[key], other[key])
      elif isinstance(self[key], datetime):
        self[key] = TEST_TIME
        other[key] = TEST_TIME

  def _new_eq(self: BaseModel, other: object) -> bool:
    self_dict = self.model_dump()
    other_dict = cast(BaseModel, other).model_dump()
    _replace_datetimes(self_dict, other_dict)
    _replace_datetimes(other_dict, self_dict)
    return self_dict == other_dict

  cls.__eq__ = _new_eq  # type: ignore


def fake_uuid(id: bytes) -> uuid.UUID:
  """Create a test UUID."""
  return uuid.UUID((id * 16).hex())
