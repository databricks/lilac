"""Huggingface source."""
import multiprocessing
from typing import Iterable, Optional, Union

import tensorflow as tf
from pydantic import (
    BaseModel,
    Field as PydanticField,
)
from typing_extensions import override

# mypy: disable-error-code="attr-defined"
from datasets import ClassLabel, DatasetDict, Sequence, Value, load_dataset, load_from_disk

from ...schema import (
    PARQUET_FILENAME_PREFIX,
    UUID_COLUMN,
    DataType,
    Field,
    Item,
    Schema,
    arrow_dtype_to_dtype,
)
from ...tasks import TaskId, progress
from ..dataset_utils import write_items_to_parquet
from .source import Source, SourceProcessResult

TFDSElement = Union[dict, tf.RaggedTensor, tf.Tensor]

HF_SPLIT_COLUMN = '__hfsplit__'

# Used when the dataset is saved locally.
DEFAULT_LOCAL_SPLIT_NAME = 'default'


class SchemaInfo(BaseModel):
  """Information about the processed huggingface schema."""
  data_schema: Schema
  class_labels: dict[str, list[str]]
  num_items: int


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
      for feature_name in class_labels.keys():
        if feature_name in example:
          example[feature_name] = class_labels[feature_name][example[feature_name]]

      # Inject the split name.
      example[HF_SPLIT_COLUMN] = split_name

      yield example


def _infer_field(feature_value: Union[Value, dict]) -> Field:
  """Infer the field type from the feature value."""
  if isinstance(feature_value, dict):
    return Field(
        dtype=DataType.STRUCT,
        fields={name: _infer_field(value) for name, value in feature_value.items()})
  elif isinstance(feature_value, Value):
    return Field(dtype=arrow_dtype_to_dtype(feature_value.pa_type))
  elif isinstance(feature_value, Sequence):
    # Huggingface Sequences can contain a dictionary of feature values, e.g.
    #   Sequence(feature={'x': Value(dtype='int32'), 'y': Value(dtype='float32')}}
    # These are converted to {'x': [...]} and {'y': [...]}
    if isinstance(feature_value.feature, dict):
      return Field(
          dtype=DataType.STRUCT,
          fields={
              name: Field(repeated_field=_infer_field(value))
              for name, value in feature_value.feature.items()
          })
    else:
      return Field(dtype=DataType.LIST, repeated_field=_infer_field(feature_value.feature))

  elif isinstance(feature_value, ClassLabel):
    raise ValueError('Nested ClassLabel is not supported.')

  else:
    raise ValueError(f'Feature is not a `Value`, `Sequence`, or `dict`: {feature_value}')


def _hf_schema_to_schema(hf_dataset_dict: DatasetDict, split: Optional[str]) -> SchemaInfo:
  """Convert the HuggingFace schema to our schema."""
  if split:
    split_datasets = [hf_dataset_dict[split]]
  else:
    split_datasets = [hf_dataset_dict[split] for split in hf_dataset_dict.keys()]

  fields: dict[str, Field] = {}
  class_labels: dict[str, list[str]] = {}
  num_items = 0

  for split_dataset in split_datasets:
    num_items += len(split_dataset)
    features = split_dataset.features
    for feature_name, feature_value in features.items():
      if feature_name in fields:
        continue

      if isinstance(feature_value, ClassLabel):
        # Class labels act as strings and we map the integer to a string before writing.
        fields[feature_name] = Field(dtype=DataType.STRING)
        class_labels[feature_name] = feature_value.names
      else:
        fields[feature_name] = _infer_field(feature_value)

  # Add the split column to the schema.
  fields[HF_SPLIT_COLUMN] = Field(dtype=DataType.STRING)
  # Add UUID to the Schema.
  fields[UUID_COLUMN] = Field(dtype=DataType.STRING)

  return SchemaInfo(
      data_schema=Schema(fields=fields), class_labels=class_labels, num_items=num_items)


class HuggingFaceDataset(Source):
  """HuggingFace data loader

  For a list of datasets see: [https://huggingface.co/datasets](https://huggingface.co/datasets).

  For documentation on dataset loading see:
      [https://huggingface.co/docs/datasets/index](https://huggingface.co/docs/datasets/index)
  """ # noqa: D415, D400
  name = 'huggingface'

  dataset_name: str
  config_name: Optional[str] = PydanticField(
      description='HuggingFace dataset config. Some datasets require this.', default=None)
  split: Optional[str] = PydanticField(
      description='HuggingFace dataset split. Loads all splits by default.', default=None)
  revision: Optional[str] = PydanticField(description='HuggingFace dataset revision.', default=None)
  load_from_disk: Optional[bool] = PydanticField(
      description='Load from local disk instead of the hub.', default=False)

  @override
  def process(
      self,
      output_dir: str,
      task_id: Optional[TaskId] = None,
  ) -> SourceProcessResult:
    """Process the source upload request."""
    if self.load_from_disk:
      # Load from disk.
      hf_dataset_dict = {DEFAULT_LOCAL_SPLIT_NAME: load_from_disk(self.dataset_name)}
    else:
      hf_dataset_dict = load_dataset(
          self.dataset_name, self.config_name, num_proc=multiprocessing.cpu_count())

    schema_info = _hf_schema_to_schema(hf_dataset_dict, self.split)

    items = progress(
        _convert_to_items(hf_dataset_dict, schema_info.class_labels, self.split),
        task_id=task_id,
        estimated_len=schema_info.num_items)

    filepath, num_items = write_items_to_parquet(
        items=items,
        output_dir=output_dir,
        schema=schema_info.data_schema,
        filename_prefix=PARQUET_FILENAME_PREFIX,
        shard_index=0,
        num_shards=1)

    return SourceProcessResult(
        filepaths=[filepath], data_schema=schema_info.data_schema, images=None, num_items=num_items)
