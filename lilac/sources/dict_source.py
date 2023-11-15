"""Dictionary source."""
import json
from typing import Any, ClassVar, Iterable, Optional, cast

import duckdb
import fsspec
import pyarrow as pa
from typing_extensions import override

from ..schema import Item, arrow_schema_to_schema
from ..source import Source, SourceSchema

_TMP_FILENAME = 'tmp.jsonl'


class DictSource(Source):
  """Loads data from an iterable of dict objects."""

  name: ClassVar[str] = 'dict'

  _items: Iterable[Item]
  _source_schema: Optional[SourceSchema] = None
  _reader: Optional[pa.RecordBatchReader] = None
  _con: Optional[duckdb.DuckDBPyConnection] = None
  _fs: fsspec.AbstractFileSystem

  def __init__(self, items: Iterable[Item], **kwargs: Any):
    super().__init__(**kwargs)
    self._items = items

  @override
  def setup(self) -> None:
    assert self._items is not None, 'items must be set.'

    # Write the items to a temporary jsonl file in memory so we can read it via duckdb.
    self._fs = fsspec.filesystem('memory')
    with self._fs.open(_TMP_FILENAME, 'w') as file:
      for item in self._items:
        json.dump(item, file)
        file.write('\n')
    del self._items

    # Register the memory filesystem to query it.
    self._con = duckdb.connect(database=':memory:')
    self._con.register_filesystem(self._fs)
    self._con.execute(
      f"""
      CREATE VIEW t as (
        SELECT * FROM read_json_auto(
          'memory://{_TMP_FILENAME}',
          IGNORE_ERRORS=true,
          FORMAT='newline_delimited'
        )
      );
    """
    )

    res = self._con.execute('SELECT COUNT(*) FROM t').fetchone()
    num_items = cast(tuple[int], res)[0]

    self._reader = self._con.execute('SELECT * from t').fetch_record_batch(rows_per_batch=10_000)
    # Create the source schema in prepare to share it between process and source_schema.
    schema = arrow_schema_to_schema(self._reader.schema)
    self._source_schema = SourceSchema(fields=schema.fields, num_items=num_items)

  @override
  def source_schema(self) -> SourceSchema:
    """Return the source schema."""
    assert self._source_schema is not None
    return self._source_schema

  @override
  def yield_items(self) -> Iterable[Item]:
    """Process the source request."""
    if not self._reader or not self._con:
      raise RuntimeError('JSON source is not initialized.')

    for batch in self._reader:
      yield from batch.to_pylist()

    self._reader.close()
    self._con.close()
    self._fs.rm(_TMP_FILENAME)
    del self._fs
