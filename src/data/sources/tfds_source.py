"""TFDS source."""
import time
from typing import Optional, Union

import numpy as np
import tensorflow as tf
import tensorflow_datasets as tfds
from pydantic import BaseModel
from pydantic import Field as PydanticField

from ...schema import PARQUET_FILENAME_PREFIX, UUID_COLUMN, DataType, Field, Item, Schema
from ...tasks import TaskStepId
from ...utils import log
from ..dataset_utils import write_items_to_parquet
from .source import Source, SourceProcessResult

TFDSElement = Union[dict, tf.RaggedTensor, tf.Tensor]


class ShardInfo(BaseModel):
  """Information about an individual source file shard."""
  dataset_name: str
  split: str
  data_schema: Schema
  shard_index: int
  num_shards: int
  output_dir: str


def _convert_to_item(tfds_element: TFDSElement) -> Item:
  if isinstance(tfds_element, dict):
    return {name: _convert_to_item(sub_element) for name, sub_element in tfds_element.items()}
  elif isinstance(tfds_element, tf.RaggedTensor):
    return tfds_element.to_list()
  elif isinstance(tfds_element, tf.Tensor):
    rank = tf.rank(tfds_element).numpy()
    if rank > 1:
      # Flatten the tensor.
      tfds_element = tf.reshape(tfds_element, [-1])
    return tfds_element.numpy()
  else:
    raise ValueError(
      f'Failed to convert TFDS element to py object: unknown type: "{type(tfds_element)}"')


def _tf_dtype_to_dtype(dtype: tf.DType) -> DataType:
  """Convert a TF dtype to pyarrow dtype."""
  # Floats.
  if dtype == tf.float16:
    return DataType.FLOAT16
  elif dtype == tf.float32:
    return DataType.FLOAT32
  elif dtype == tf.float64:
    return DataType.FLOAT64
  # Ints.
  elif dtype == tf.int8:
    return DataType.INT8
  elif dtype == tf.int16:
    return DataType.INT16
  elif dtype == tf.int32:
    return DataType.INT32
  elif dtype == tf.int64:
    return DataType.INT64
  elif dtype == tf.uint8:
    return DataType.UINT8
  elif dtype == tf.uint16:
    return DataType.UINT16
  elif dtype == tf.uint32:
    return DataType.UINT32
  elif dtype == tf.uint64:
    return DataType.UINT64
  elif dtype.is_bool:
    return DataType.BOOLEAN
  elif dtype == tf.string:
    return DataType.STRING
  else:
    raise ValueError(f'Cannot convert TF dtype to dtype. Unsupported TF dtype: "{dtype}"')


def _tfds_subschema_to_field(feature: tfds.features.FeatureConnector) -> Union[Field, None]:
  # Handle composite features.
  if isinstance(feature, tfds.features.FeaturesDict):
    fields: dict[str, Field] = {}
    for name, sub_feature in feature.items():
      field = _tfds_subschema_to_field(sub_feature)
      if field:
        fields[name] = field
    return Field(fields=fields)
  elif isinstance(feature, tfds.features.Sequence):
    field = _tfds_subschema_to_field(feature.feature)
    if field:
      return Field(repeated_field=field)
    else:
      return None
  # Handle primitives.
  elif isinstance(feature, tfds.features.Tensor):
    rank = len(feature.shape)
    if rank > 1:
      log(f'Feature "{feature}" has a higher rank tensor with shape {feature.shape}: will flatten')
      # TODO(smilkov): Store the original shape somewhere in parquet column metadata.
    dtype = _tf_dtype_to_dtype(feature.dtype)
    size = np.prod(feature.shape)
    field = Field(dtype=dtype)
    if size > 1:
      return Field(repeated_field=field)
    else:
      return field
  else:
    log(f'Skipping feature "{feature}": type "{type(feature)}" is not supported.')
    return None


def _tfds_schema_to_schema(feature: tfds.features.FeaturesDict) -> Schema:
  """Convert the TFDS schema to our schema."""
  # Handle composite features.
  fields: dict[str, Field] = {}
  for name, sub_feature in feature.items():
    field = _tfds_subschema_to_field(sub_feature)
    if field:
      fields[name] = field

  # Add UUID to the Schema.
  fields[UUID_COLUMN] = Field(dtype=DataType.STRING)

  return Schema(fields=fields)


class ShardOut(BaseModel):
  """The result of a single shard of a source dataset."""
  filepath: str
  num_items: int


class TensorFlowDataset(Source):
  """TensorFlow datasets data loader

  For a list of datasets see:
    [https://www.tensorflow.org/datasets/catalog/overview](https://www.tensorflow.org/datasets/catalog/overview).

  For documentation on dataset loading see:
      [https://www.tensorflow.org/datasets/overview](https://www.tensorflow.org/datasets/overview)
  """ # noqa: D415, D400
  name = 'tfds'

  tfds_name: str
  split: Optional[str] = PydanticField(
    default=None,
    description='The TensorFlow dataset split name. If not provided, loads all splits.')

  def process(
    self,
    output_dir: str,
    task_step_id: Optional[TaskStepId] = None,
  ) -> SourceProcessResult:
    """Process the source upload request."""
    builder = tfds.builder(self.tfds_name)
    split = list(builder.info.splits.keys())[0]
    if self.split:
      split = self.split
    elif 'train' in builder.info.splits:
      split = 'train'
    log(f'TFDS({self.tfds_name}): Using split "{split}"')

    if not builder.info.splits.total_num_examples:
      raise ValueError(f'No examples found in {builder.name!r}. Was the dataset generated ?')

    if not tf.io.gfile.exists(builder._data_dir):
      log(f'Downloading and preparing "{builder.name}"...')
      start_time = time.time()
      builder.download_and_prepare()
      elapsed = time.time() - start_time
      log(f'Download and prepare of "{builder.name}" took {elapsed:.2f} seconds.')

    schema = _tfds_schema_to_schema(builder.info.features)
    num_shards = builder.info.splits[split].num_shards
    shard_infos = [
      ShardInfo(
        dataset_name=self.tfds_name,
        split=split,
        data_schema=schema,
        shard_index=shard_index,
        num_shards=num_shards,
        output_dir=output_dir) for shard_index in range(num_shards)
    ]

    # TODO(nsthorat): Use dask to parallelize this if we ever use TFDS again.
    shard_outs = [self.process_shard(shard_info) for shard_info in shard_infos]
    filepaths = [shard_out.filepath for shard_out in shard_outs]
    num_items = sum(shard_out.num_items for shard_out in shard_outs)

    return SourceProcessResult(
      filepaths=filepaths, data_schema=schema, images=None, num_items=num_items)

  def process_shard(self, shard_info: ShardInfo) -> ShardOut:
    """Process an input file shard. Each shard is processed in parallel by different workers."""
    ds = tfds.load(
      shard_info.dataset_name, split=f'{shard_info.split}[{shard_info.shard_index}shard]')

    ds = ds.prefetch(10_000)
    items = (_convert_to_item(tfds_element) for tfds_element in ds)
    filepath, num_items = write_items_to_parquet(
      items=items,
      output_dir=shard_info.output_dir,
      schema=shard_info.data_schema,
      filename_prefix=PARQUET_FILENAME_PREFIX,
      shard_index=shard_info.shard_index,
      num_shards=shard_info.num_shards)
    return ShardOut(filepath=filepath, num_items=num_items)
