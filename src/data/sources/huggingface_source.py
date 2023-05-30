"""Huggingface source."""
import multiprocessing
from typing import Iterable, Optional, Union

import numpy as np
from pydantic import BaseModel
from pydantic import Field as PydanticField
from typing_extensions import override

# mypy: disable-error-code="attr-defined"
from datasets import ClassLabel, DatasetDict, Sequence, Value, load_dataset, load_from_disk

from ...schema import DataType, Field, Item, arrow_dtype_to_dtype
from .source import Source, SourceSchema

HF_SPLIT_COLUMN = '__hfsplit__'

# Used when the dataset is saved locally.
DEFAULT_LOCAL_SPLIT_NAME = 'default'


class SchemaInfo(BaseModel):
  """Information about the processed huggingface schema."""
  fields: dict[str, Field] = {}
  class_labels: dict[str, list[str]]
  num_items: int


def _infer_field(feature_value: Union[Value, dict]) -> Field:
  """Infer the field type from the feature value."""
  if isinstance(feature_value, dict):
    return Field(fields={name: _infer_field(value) for name, value in feature_value.items()})
  elif isinstance(feature_value, Value):
    return Field(dtype=arrow_dtype_to_dtype(feature_value.pa_type))
  elif isinstance(feature_value, Sequence):
    # Huggingface Sequences can contain a dictionary of feature values, e.g.
    #   Sequence(feature={'x': Value(dtype='int32'), 'y': Value(dtype='float32')}}
    # These are converted to {'x': [...]} and {'y': [...]}
    if isinstance(feature_value.feature, dict):
      return Field(
        fields={
          name: Field(repeated_field=_infer_field(value))
          for name, value in feature_value.feature.items()
        })
    else:
      return Field(repeated_field=_infer_field(feature_value.feature))

  elif isinstance(feature_value, ClassLabel):
    raise ValueError('Nested ClassLabel is not supported.')

  else:
    raise ValueError(f'Feature is not a `Value`, `Sequence`, or `dict`: {feature_value}')


def hf_schema_to_schema(hf_dataset_dict: DatasetDict, split: Optional[str]) -> SchemaInfo:
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

  return SchemaInfo(fields=fields, class_labels=class_labels, num_items=num_items)


class HuggingFaceDataset(Source):
  """HuggingFace data loader

  For a list of datasets see: [huggingface.co/datasets](https://huggingface.co/datasets).

  For documentation on dataset loading see:
      [huggingface.co/docs/datasets/index](https://huggingface.co/docs/datasets/index)
  """ # noqa: D415, D400
  name = 'huggingface'

  dataset_name: str = PydanticField(
    required=True,
    description='Either in the format `user/dataset` or `dataset`.',
  )
  config_name: Optional[str] = PydanticField(
    title='Dataset config name', description='Some datasets require this.', default=None)
  split: Optional[str] = PydanticField(
    title='Dataset split', description='Loads all splits by default.', default=None)
  revision: Optional[str] = PydanticField(title='Dataset revision', default=None)
  load_from_disk: Optional[bool] = PydanticField(
    description='Load from local disk instead of the hub.', default=False)

  _dataset_dict: DatasetDict
  _schema_info: SchemaInfo

  @override
  def prepare(self) -> None:
    if self.load_from_disk:
      # Load from disk.
      hf_dataset_dict = {DEFAULT_LOCAL_SPLIT_NAME: load_from_disk(self.dataset_name)}
    else:
      hf_dataset_dict = load_dataset(
        self.dataset_name, self.config_name, num_proc=multiprocessing.cpu_count())
    self._dataset_dict = hf_dataset_dict
    self._schema_info = hf_schema_to_schema(self._dataset_dict, self.split)

  @override
  def source_schema(self) -> SourceSchema:
    return SourceSchema(fields=self._schema_info.fields, num_items=self._schema_info.num_items)

  @override
  def process(self) -> Iterable[Item]:
    if self.split:
      split_names = [self.split]
    else:
      split_names = list(self._dataset_dict.keys())

    for split_name in split_names:
      split_dataset = self._dataset_dict[split_name]

      for example in split_dataset:
        # Replace the class labels with strings.
        for feature_name in self._schema_info.class_labels.keys():
          if feature_name in example:
            example[feature_name] = self._schema_info.class_labels[feature_name][
              example[feature_name]]

        # Inject the split name.
        example[HF_SPLIT_COLUMN] = split_name

        # Huggingface Sequences are represented as np.arrays. Convert them to lists.
        example = _np_array_to_list_deep(example)

        yield example


def _np_array_to_list_deep(item: Item) -> Item:
  """Convert all numpy arrays to lists."""
  for key, value in item.items():
    if isinstance(value, np.ndarray):
      item[key] = value.tolist()
    elif isinstance(value, dict):
      item[key] = _np_array_to_list_deep(value)
  return item
