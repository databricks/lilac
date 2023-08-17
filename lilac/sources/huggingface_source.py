"""Huggingface source."""
import multiprocessing
from typing import Iterable, Optional, Union

import numpy as np
from datasets import (
  ClassLabel,
  DatasetDict,
  Image,
  Sequence,
  Translation,
  Value,
  load_dataset,
  load_from_disk,
)
from pydantic import BaseModel
from pydantic import Field as PydanticField
from typing_extensions import override

from ..schema import DataType, Field, Item, arrow_dtype_to_dtype
from ..utils import log
from .source import Source, SourceSchema

HF_SPLIT_COLUMN = '__hfsplit__'

# Used when the dataset is saved locally.
DEFAULT_LOCAL_SPLIT_NAME = 'default'


class SchemaInfo(BaseModel):
  """Information about the processed huggingface schema."""
  fields: dict[str, Field] = {}
  class_labels: dict[str, list[str]]
  num_items: int


def _infer_field(feature_value: Union[Value, dict]) -> Optional[Field]:
  """Infer the field type from the feature value."""
  if isinstance(feature_value, dict):
    fields: dict[str, Field] = {}
    for name, value in feature_value.items():
      field = _infer_field(value)
      if field:
        fields[name] = field
    return Field(fields=fields)
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
  elif isinstance(feature_value, list):
    if len(feature_value) > 1:
      raise ValueError('Field arrays with multiple values are not supported.')
    return Field(repeated_field=_infer_field(feature_value[0]))
  elif isinstance(feature_value, ClassLabel):
    # TODO(nsthorat): For nested class labels, return the path with the class label values to show
    # strings in the UI.
    return Field(dtype=DataType.INT32)
  elif isinstance(feature_value, Image):
    log(f'{feature_value} has type Image and is ignored.')
    return None
  else:
    raise ValueError(f'Feature is not a `Value`, `Sequence`, or `dict`: {feature_value}')


def hf_schema_to_schema(hf_dataset_dict: DatasetDict, split: Optional[str],
                        sample_size: Optional[int]) -> SchemaInfo:
  """Convert the HuggingFace schema to our schema."""
  if split:
    split_datasets = [hf_dataset_dict[split]]
  else:
    split_datasets = [hf_dataset_dict[split] for split in hf_dataset_dict.keys()]

  fields: dict[str, Field] = {}
  class_labels: dict[str, list[str]] = {}
  num_items = 0

  for split_dataset in split_datasets:
    split_size = len(split_dataset)
    if sample_size:
      split_size = min(split_size, sample_size)
    num_items += split_size

    features = split_dataset.features
    for feature_name, feature_value in features.items():
      if feature_name in fields:
        continue

      if isinstance(feature_value, ClassLabel):
        # Class labels act as strings and we map the integer to a string before writing.
        fields[feature_name] = Field(dtype=DataType.STRING)
        class_labels[feature_name] = feature_value.names
      elif isinstance(feature_value, Translation):
        # Translations act as categorical strings.
        language_fields: dict[str, Field] = {}
        for language in feature_value.languages:
          language_fields[language] = Field(dtype=DataType.STRING)
        fields[feature_name] = Field(fields=language_fields)
      else:
        field = _infer_field(feature_value)
        if field:
          fields[feature_name] = field

  # Add the split column to the schema.
  fields[HF_SPLIT_COLUMN] = Field(dtype=DataType.STRING)

  return SchemaInfo(fields=fields, class_labels=class_labels, num_items=num_items)


class HuggingFaceSource(Source):
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
  sample_size: Optional[int] = PydanticField(
    title='Sample size',
    description='Number of rows to sample from the dataset, for each split.',
    default=None)
  revision: Optional[str] = PydanticField(title='Dataset revision', default=None)
  load_from_disk: Optional[bool] = PydanticField(
    description='Load from local disk instead of the hub.', default=False)

  _dataset_dict: Optional[DatasetDict] = None
  _schema_info: Optional[SchemaInfo] = None

  @override
  def setup(self) -> None:
    if self.load_from_disk:
      # Load from disk.
      hf_dataset_dict = {DEFAULT_LOCAL_SPLIT_NAME: load_from_disk(self.dataset_name)}
    else:
      hf_dataset_dict = load_dataset(
        self.dataset_name,
        self.config_name,
        num_proc=multiprocessing.cpu_count(),
        ignore_verifications=True)
    self._dataset_dict = hf_dataset_dict
    self._schema_info = hf_schema_to_schema(self._dataset_dict, self.split, self.sample_size)

  @override
  def source_schema(self) -> SourceSchema:
    if not self._schema_info:
      raise ValueError('`setup()` must be called before `source_schema`.')
    return SourceSchema(fields=self._schema_info.fields, num_items=self._schema_info.num_items)

  @override
  def process(self) -> Iterable[Item]:
    if not self._schema_info or not self._dataset_dict:
      raise ValueError('`setup()` must be called before `process`.')

    if self.split:
      split_names = [self.split]
    else:
      split_names = list(self._dataset_dict.keys())

    for split_name in split_names:
      split_dataset = self._dataset_dict[split_name]
      if self.sample_size:
        split_dataset = split_dataset.select(range(self.sample_size))

      for example in split_dataset:
        # Replace the label maps with strings.
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
