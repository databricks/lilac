"""Tests for load.py: loading project configs."""

import os
import pathlib
import re
from typing import ClassVar, Iterable, Iterator, Optional, cast

import numpy as np
import pytest
from pytest_mock import MockerFixture
from typing_extensions import override

from .config import (
  ClusterConfig,
  ClusterInputSelectorConfig,
  Config,
  DatasetConfig,
  EmbeddingConfig,
  SignalConfig,
)
from .data import cluster_titling
from .data.dataset import DatasetManifest
from .db_manager import get_dataset
from .embeddings.jina import JinaV2Small
from .env import set_project_dir
from .load import load
from .project import PROJECT_CONFIG_FILENAME, init
from .schema import (
  EMBEDDING_KEY,
  EmbeddingInfo,
  Field,
  Item,
  RichData,
  chunk_embedding,
  field,
  schema,
)
from .signal import (
  TextEmbeddingSignal,
  TextSignal,
  clear_signal_registry,
  register_embedding,
  register_signal,
)
from .source import Source, SourceSchema, clear_source_registry, register_source
from .utils import to_yaml

SIMPLE_ITEMS: list[Item] = [
  {'str': 'a', 'int': 1, 'bool': False, 'float': 3.0},
  {'str': 'b', 'int': 2, 'bool': True, 'float': 2.0},
  {'str': 'c', 'int': 3, 'bool': True, 'float': 1.0},
]

EMBEDDINGS: list[tuple[str, list[float]]] = [
  ('a', [1.0, 0.0, 0.0]),
  ('b', [1.0, 1.0, 0.0]),
  ('c', [1.0, 1.0, 0.0]),
]

STR_EMBEDDINGS: dict[str, list[float]] = {text: embedding for text, embedding in EMBEDDINGS}


class TestSource(Source):
  """A test source."""

  name: ClassVar[str] = 'test_source'

  @override
  def source_schema(self) -> SourceSchema:
    """Yield all items."""
    return SourceSchema(
      fields={
        'str': field('string'),
        'int': field('int32'),
        'bool': field('boolean'),
        'float': field('float32'),
      },
      num_items=len(SIMPLE_ITEMS),
    )

  @override
  def yield_items(self) -> Iterable[Item]:
    """Yield all items."""
    yield from SIMPLE_ITEMS


class TestEmbedding(TextEmbeddingSignal):
  """A test embed function."""

  name: ClassVar[str] = 'test_embedding'

  @override
  def compute(self, data: Iterable[RichData]) -> Iterator[Item]:
    """Call the embedding function."""
    for example in data:
      yield [chunk_embedding(0, len(example), np.array(STR_EMBEDDINGS[cast(str, example)]))]


class TestSignal(TextSignal):
  name: ClassVar[str] = 'test_signal'

  _call_count: int = 0

  def fields(self) -> Field:
    return field('int32')

  def compute(self, data: Iterable[RichData]) -> Iterator[Optional[Item]]:
    for text_content in data:
      self._call_count += 1
      yield len(text_content)


@pytest.fixture(scope='module', autouse=True)
def setup_teardown() -> Iterable[None]:
  # Setup.
  register_source(TestSource)
  register_signal(TestSignal)
  register_embedding(TestEmbedding)

  # Unit test runs.
  yield

  # Teardown.
  clear_source_registry()
  clear_signal_registry()


def test_load_config_obj(tmp_path: pathlib.Path) -> None:
  set_project_dir(tmp_path)

  # Initialize the lilac project. init() defaults to the project directory.
  init()

  project_config = Config(
    datasets=[DatasetConfig(namespace='namespace', name='test', source=TestSource())]
  )

  # Load the project config from a config object.
  load(config=project_config)

  dataset = get_dataset('namespace', 'test')

  assert dataset.manifest() == DatasetManifest(
    namespace='namespace',
    dataset_name='test',
    data_schema=schema({'str': 'string', 'int': 'int32', 'bool': 'boolean', 'float': 'float32'}),
    num_items=3,
    source=TestSource(),
  )


def test_load_project_config_yml(tmp_path: pathlib.Path) -> None:
  set_project_dir(tmp_path)

  # Initialize the lilac project. init() defaults to the project directory.
  init()

  # Simulate the user manually editing the project config.
  project_config = Config(
    datasets=[DatasetConfig(namespace='namespace', name='test', source=TestSource())]
  )
  project_config_yml = to_yaml(project_config.model_dump())
  config_path = os.path.join(tmp_path, PROJECT_CONFIG_FILENAME)

  # Write the project_config as yml to project dir.
  with open(config_path, 'w') as f:
    f.write(project_config_yml)

  load(config=config_path)

  dataset = get_dataset('namespace', 'test')

  assert dataset.manifest() == DatasetManifest(
    namespace='namespace',
    dataset_name='test',
    data_schema=schema({'str': 'string', 'int': 'int32', 'bool': 'boolean', 'float': 'float32'}),
    num_items=3,
    source=TestSource(),
  )


def test_load_config_yml_outside_project(tmp_path: pathlib.Path) -> None:
  # This test makes sure that we can load a yml file from outside the project directory.

  config_path = os.path.join(tmp_path, PROJECT_CONFIG_FILENAME)
  project_dir = os.path.join(tmp_path, 'project')
  os.makedirs(project_dir)
  set_project_dir(tmp_path)

  project_config = Config(
    datasets=[DatasetConfig(namespace='namespace', name='test', source=TestSource())]
  )

  project_config_yml = to_yaml(project_config.model_dump())

  # Write the project_config as yml to project dir.
  with open(config_path, 'w') as f:
    f.write(project_config_yml)

  load(config=config_path)

  dataset = get_dataset('namespace', 'test')

  assert dataset.manifest() == DatasetManifest(
    namespace='namespace',
    dataset_name='test',
    data_schema=schema({'str': 'string', 'int': 'int32', 'bool': 'boolean', 'float': 'float32'}),
    num_items=3,
    source=TestSource(),
  )


def test_load_signals(tmp_path: pathlib.Path) -> None:
  set_project_dir(tmp_path)

  # Initialize the lilac project. init() defaults to the project directory.
  init()

  test_signal = TestSignal()
  project_config = Config(
    datasets=[
      DatasetConfig(
        namespace='namespace',
        name='test',
        source=TestSource(),
        signals=[SignalConfig(path=('str',), signal=test_signal)],
      )
    ]
  )

  # Load the project config from a config object.
  load(config=project_config)

  dataset = get_dataset('namespace', 'test')

  assert dataset.manifest() == DatasetManifest(
    namespace='namespace',
    dataset_name='test',
    data_schema=schema(
      {
        'str': field(
          'string',
          fields={'test_signal': field('int32', signal=test_signal.model_dump(exclude_none=True))},
        ),
        'int': 'int32',
        'bool': 'boolean',
        'float': 'float32',
      }
    ),
    num_items=3,
    source=TestSource(),
  )


def test_load_embeddings(tmp_path: pathlib.Path) -> None:
  set_project_dir(tmp_path)

  # Initialize the lilac project. init() defaults to the project directory.
  init()

  project_config = Config(
    datasets=[
      DatasetConfig(
        namespace='namespace',
        name='test',
        source=TestSource(),
        embeddings=[EmbeddingConfig(path=('str',), embedding='test_embedding')],
      )
    ]
  )

  # Load the project config from a config object.
  load(config=project_config)

  dataset = get_dataset('namespace', 'test')

  assert dataset.manifest() == DatasetManifest(
    namespace='namespace',
    dataset_name='test',
    data_schema=schema(
      {
        'str': field(
          'string',
          fields={
            'test_embedding': field(
              signal=TestEmbedding().model_dump(exclude_none=True),
              fields=[field('string_span', fields={EMBEDDING_KEY: 'embedding'})],
              embedding=EmbeddingInfo(input_path=('str',), embedding='test_embedding'),
            )
          },
        ),
        'int': 'int32',
        'bool': 'boolean',
        'float': 'float32',
      }
    ),
    num_items=3,
    source=TestSource(),
  )


def test_load_twice_no_overwrite(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture) -> None:
  set_project_dir(tmp_path)

  # Initialize the lilac project. init() defaults to the project directory.
  init()

  test_signal = TestSignal()
  project_config = Config(
    datasets=[
      DatasetConfig(
        namespace='namespace',
        name='test',
        source=TestSource(),
        signals=[SignalConfig(path=('str',), signal=test_signal)],
        embeddings=[EmbeddingConfig(path=('str',), embedding='test_embedding')],
      )
    ]
  )

  # Load the project config from a config object.
  load(config=project_config)

  assert 'Computing signal' in capsys.readouterr().out

  first_manifest = get_dataset('namespace', 'test').manifest()

  # Load the project again, make sure signals and embeddings are not computed again.
  load(config=project_config)

  second_manifest = get_dataset('namespace', 'test').manifest()
  assert first_manifest == second_manifest
  assert re.search('Signal  TestSignal(.*) already exists', capsys.readouterr().out)


def test_load_twice_overwrite(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture) -> None:
  set_project_dir(tmp_path)

  # Initialize the lilac project. init() defaults to the project directory.
  init()

  test_signal = TestSignal()
  project_config = Config(
    datasets=[
      DatasetConfig(
        namespace='namespace',
        name='test',
        source=TestSource(),
        signals=[SignalConfig(path=('str',), signal=test_signal)],
        embeddings=[EmbeddingConfig(path=('str',), embedding='test_embedding')],
      )
    ]
  )

  # Load the project config from a config object.
  load(config=project_config)
  assert 'Computing signal' in capsys.readouterr().out

  first_manifest = get_dataset('namespace', 'test').manifest()

  # Load the project again, make sure signals and embeddings are not computed again.
  load(config=project_config, overwrite=True)

  assert (
    'Signal  TestSignal({"signal_name":"test_signal"}) already exists'
    not in capsys.readouterr().out
  )

  second_manifest = get_dataset('namespace', 'test').manifest()

  assert first_manifest == second_manifest


def _mock_jina(mocker: MockerFixture) -> None:
  def compute(docs: list[str]) -> list[Item]:
    result = []
    for doc in docs:
      if 'summar' in doc or 'hello' in doc or 'greeting' in doc:
        result.append([chunk_embedding(0, len(doc), np.array([1, 1, 1]))])
      elif 'simpl' in doc or 'whats' in doc or 'time' in doc:
        result.append([chunk_embedding(0, len(doc), np.array([0, 0, 0]))])
      else:
        result.append([chunk_embedding(0, len(doc), np.array([0.5, 0.5, 0.5]))])
    return result

  mocker.patch.object(JinaV2Small, 'compute', side_effect=compute)
  mocker.patch.object(JinaV2Small, 'setup', return_value=None)


def test_load_clusters(
  tmp_path: pathlib.Path, capsys: pytest.CaptureFixture, mocker: MockerFixture
) -> None:
  set_project_dir(tmp_path)

  # Initialize the lilac project. init() defaults to the project directory.
  init()

  project_config = Config(
    datasets=[
      DatasetConfig(
        namespace='namespace',
        name='test',
        source=TestSource(),
      )
    ],
    clusters=[
      ClusterConfig(dataset_namespace='namespace', dataset_name='test', input_path=('str',))
    ],
  )

  _mock_jina(mocker)
  mocker.patch.object(cluster_titling, 'generate_title_openai', return_value='title')
  mocker.patch.object(cluster_titling, 'generate_category_openai', return_value='category')

  _mock_jina(mocker)

  # Load the project config from a config object.
  load(config=project_config)
  assert 'Computing cluster:' in capsys.readouterr().out

  dataset = get_dataset('namespace', 'test')
  assert dataset.manifest().data_schema.fields['str__cluster'].cluster is not None

  load(config=project_config)
  assert 'Cluster already computed:' in capsys.readouterr().out


class TestShareGPTSource(Source):
  """A test sharegpt source."""

  name: ClassVar[str] = 'test_sharegpt_source'

  @override
  def source_schema(self) -> SourceSchema:
    """Yield all items."""
    return SourceSchema(
      fields=schema(
        {
          'conversations': [
            {
              'from': 'string',
              'value': 'string',
            }
          ]
        }
      ).fields,
      num_items=4,
    )

  @override
  def yield_items(self) -> Iterable[Item]:
    """Yield all items."""
    yield from [
      {
        'conversations': [
          {'from': 'human', 'value': 'hello'},
          {'from': 'gpt', 'value': 'i am a language model'},
        ]
      },
      {
        'conversations': [
          {'from': 'human', 'value': 'whats the time'},
          {'from': 'gpt', 'value': '1030'},
        ]
      },
      {
        'conversations': [
          {'from': 'human', 'value': 'hello how are you'},
          {'from': 'gpt', 'value': 'pretty good today'},
        ]
      },
      {
        'conversations': [
          {'from': 'human', 'value': 'whats the hour'},
          {'from': 'gpt', 'value': '10 is the hour'},
        ]
      },
    ]


def test_load_clusters_format_selector(
  tmp_path: pathlib.Path, capsys: pytest.CaptureFixture, mocker: MockerFixture
) -> None:
  mocker.patch.object(cluster_titling, 'generate_category_openai', return_value='MockCategory')
  _mock_jina(mocker)

  topic_fn_calls: list[list[tuple[str, float]]] = []

  def _test_topic_fn(docs: list[tuple[str, float]]) -> str:
    topic_fn_calls.append(docs)
    if 'hello' in docs[0][0]:
      return 'greeting'
    elif 'time' in docs[0][0] or 'hour' in docs[0][0]:
      return 'time'
    return 'other'

  mocker.patch.object(cluster_titling, 'generate_title_openai', side_effect=_test_topic_fn)
  set_project_dir(tmp_path)

  # Initialize the lilac project. init() defaults to the project directory.
  init()

  project_config = Config(
    datasets=[
      DatasetConfig(
        namespace='namespace',
        name='test',
        source=TestShareGPTSource(),
      )
    ],
    clusters=[
      ClusterConfig(
        dataset_namespace='namespace',
        dataset_name='test',
        input_selector=ClusterInputSelectorConfig(
          format='sharegpt',
          selector='human',
        ),
        output_path=('cluster',),
        min_cluster_size=2,
      )
    ],
  )

  # Load the project config from a config object.
  load(config=project_config)
  assert 'Computing cluster:' in capsys.readouterr().out

  # Sort because topics are shuffled.
  for topic_fn_call in topic_fn_calls:
    topic_fn_call.sort()

  # Make sure the topic function is only called for the human text.
  assert topic_fn_calls == [
    [('hello', 1.0), ('hello how are you', 1.0)],
    [('whats the hour', 1.0), ('whats the time', 1.0)],
  ]

  load(config=project_config)
  assert 'Cluster already computed:' in capsys.readouterr().out
