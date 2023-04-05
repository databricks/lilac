"""Huggingface source."""
import multiprocessing
from typing import Iterable, Optional, Union

import tensorflow as tf
from pydantic import BaseModel
from typing_extensions import override

from datasets import ClassLabel, DatasetDict, Value, load_dataset

from ...schema import (
    PARQUET_FILENAME_PREFIX,
    UUID_COLUMN,
    DataType,
    Field,
    Item,
    Schema,
    arrow_dtype_to_dtype,
)
from ...utils import write_items_to_parquet
from .source import ShardsLoader, Source, SourceProcessResult, SourceShardOut

TFDSElement = Union[dict, tf.RaggedTensor, tf.Tensor]

HF_SPLIT_COLUMN = '__hfsplit__'


class SchemaInfo(BaseModel):
  """Information about the processed huggingface schema."""
  data_schema: Schema
  class_labels: dict[str, list[str]]


class ShardInfo(BaseModel):
  """Information about an individual source file shard."""
  hf_dataset_name: str
  split: Optional[str]
  schema_info: SchemaInfo
  output_dir: str


def _convert_to_items(hf_dataset_dict: DatasetDict, class_labels: dict[str, list[str]],
                      split: Optional[str]) -> Iterable[Item]:
  """Convert a huggingface split datasets to an iterable of items."""
  if split:
    split_names = [split]
  else:
    split_names = list(hf_dataset_dict.keys())

  for split_name in split_names:
    split_dataset = hf_dataset_dict[split_name]
    for example in split_dataset:
      # Replace the class labels with strings.
      for feature_name, label in class_labels.items():
        if feature_name in example:
          example[feature_name] = class_labels[feature_name][example[feature_name]]

      # Inject the split name.
      example[HF_SPLIT_COLUMN] = split_name

      yield example


def _hf_schema_to_schema(hf_dataset_dict: DatasetDict, split: Optional[str]) -> SchemaInfo:
  """Convert the TFDS schema to our schema."""
  if split:
    split_datasets = [hf_dataset_dict[split]]
  else:
    split_datasets = [hf_dataset_dict[split] for split in hf_dataset_dict.keys()]

  fields: dict[str, Field] = {}
  class_labels: dict[str, list[str]] = {}

  for split_dataset in split_datasets:
    features = split_dataset.features
    for feature_name, feature_value in features.items():
      if feature_name in fields:
        continue

      # We currently don't support recursive structures.
      if not isinstance(feature_value, (ClassLabel, Value)):
        raise ValueError(f'Feature "{feature_name}" is not a Value or ClassLabel: {feature_value}')

      if isinstance(feature_value, Value):
        fields[feature_name] = Field(dtype=arrow_dtype_to_dtype(feature_value.pa_type))
      elif isinstance(feature_value, ClassLabel):
        # Class labels act as strings and we map the integer to a string before writing.
        fields[feature_name] = Field(dtype=DataType.STRING)
        class_labels[feature_name] = feature_value.names

  # Add the split column to the schema.
  fields[HF_SPLIT_COLUMN] = Field(dtype=DataType.STRING)
  # Add UUID to the Schema.
  fields[UUID_COLUMN] = Field(dtype=DataType.BINARY)

  return SchemaInfo(data_schema=Schema(fields=fields), class_labels=class_labels)


class HuggingFaceDataset(Source[ShardInfo]):
  """Huggingface data loader."""
  name = 'huggingface'
  shard_info_cls = ShardInfo

  huggingface_dataset_name: str
  revision: Optional[str] = None
  split: Optional[str] = None

  @override
  async def process(self, output_dir: str, shards_loader: ShardsLoader) -> SourceProcessResult:
    """Process the source upload request."""
    hf_dataset_dict = load_dataset(self.huggingface_dataset_name,
                                   num_proc=multiprocessing.cpu_count())

    schema_info = _hf_schema_to_schema(hf_dataset_dict, self.split)

    shard_infos = [
        ShardInfo(hf_dataset_name=self.huggingface_dataset_name,
                  split=self.split,
                  schema_info=schema_info,
                  output_dir=output_dir)
    ]
    shard_outs = await shards_loader(shard_infos)
    filepaths = [shard_out.filepath for shard_out in shard_outs]
    num_items = sum(shard_out.num_items for shard_out in shard_outs)
    return SourceProcessResult(filepaths=filepaths,
                               data_schema=schema_info.data_schema,
                               images=None,
                               num_items=num_items)

  @override
  def process_shard(self, shard_info: ShardInfo) -> SourceShardOut:
    """Process an input file shard. Each shard is processed in parallel by different workers."""
    hf_dataset_dict = load_dataset(self.huggingface_dataset_name,
                                   num_proc=multiprocessing.cpu_count())

    print(shard_info)
    items = _convert_to_items(hf_dataset_dict, shard_info.schema_info.class_labels,
                              shard_info.split)
    filepath, num_items = write_items_to_parquet(items=items,
                                                 output_dir=shard_info.output_dir,
                                                 schema=shard_info.schema_info.data_schema,
                                                 filename_prefix=PARQUET_FILENAME_PREFIX,
                                                 shard_index=0,
                                                 num_shards=1)
    return SourceShardOut(filepath=filepath, num_items=num_items)
