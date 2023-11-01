"""A Parquet file writer that wraps the pyarrow writer."""
from typing import IO, Optional

import pyarrow as pa
import pyarrow.parquet as pq

from .schema import Item, Schema, schema_to_arrow_schema


class ParquetWriter:
  """A writer to parquet."""

  def __init__(
    self,
    schema: Schema,
    codec: str = 'snappy',
    row_group_buffer_size: int = 128 * 1024 * 1024,
    record_batch_size: int = 10_000,
  ):
    self._schema = schema_to_arrow_schema(schema)
    self._codec = codec
    self._row_group_buffer_size = row_group_buffer_size
    self._buffer: list[list[Optional[Item]]] = [[] for _ in range(len(self._schema.names))]
    self._buffer_size = record_batch_size
    self._record_batches: list[pa.RecordBatch] = []
    self._record_batches_byte_size = 0
    self.writer: pq.ParquetWriter = None

  def open(self, file_handle: IO) -> None:
    """Open the destination file for writing."""
    self.writer = pq.ParquetWriter(file_handle, self._schema, compression=self._codec)

  def write(self, record: Item) -> None:
    """Write the record to the destination file."""
    if len(self._buffer[0]) >= self._buffer_size:
      self._flush_buffer()

    if self._record_batches_byte_size >= self._row_group_buffer_size:
      self._write_batches()

    # reorder the data in columnar format.
    for i, n in enumerate(self._schema.names):
      self._buffer[i].append(record.get(n))

  def close(self) -> None:
    """Flushes the write buffer and closes the destination file."""
    if len(self._buffer[0]) > 0:
      self._flush_buffer()
    if self._record_batches_byte_size > 0:
      self._write_batches()

    self.writer.close()

  def _write_batches(self) -> None:
    table = pa.Table.from_batches(self._record_batches, schema=self._schema)
    self._record_batches = []
    self._record_batches_byte_size = 0
    self.writer.write_table(table)

  def _flush_buffer(self) -> None:
    arrays: list[pa.array] = [[] for _ in range(len(self._schema.names))]
    for x, y in enumerate(self._buffer):
      arrays[x] = pa.array(y, type=self._schema.types[x])
      self._buffer[x] = []
    rb = pa.RecordBatch.from_arrays(arrays, schema=self._schema)
    self._record_batches.append(rb)
    size = 0
    for x in arrays:
      for b in x.buffers():  # type: ignore
        if b is not None:
          size = size + b.size
    self._record_batches_byte_size = self._record_batches_byte_size + size
