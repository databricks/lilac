"""A data loader standalone binary. This should only be run as a script to load a dataset.

To run the source loader as a binary directly:

poetry run python -m src.data_loader \
  --dataset_name=$DATASET \
  --output_dir=./gcs_cache/ \
  --config_path=./datasets/the_movies_dataset.json
"""
import json
import os
from typing import Optional

import click
from distributed import Client

from .data.sources.default_sources import register_default_sources
from .data.sources.source import Source
from .data.sources.source_registry import resolve_source
from .schema import MANIFEST_FILENAME, SourceManifest
from .tasks import TaskId
from .utils import DebugTimer, get_dataset_output_dir, log, open_file


def process_source(base_dir: str,
                   namespace: str,
                   dataset_name: str,
                   source: Source,
                   task_id: Optional[TaskId] = None) -> tuple[str, int]:
  """Process a source."""
  output_dir = get_dataset_output_dir(base_dir, namespace, dataset_name)

  with DebugTimer(f'[{source.name}] Processing dataset "{dataset_name}"'):
    source_process_result = source.process(output_dir, task_id)

  filenames = [os.path.basename(filepath) for filepath in source_process_result.filepaths]
  manifest = SourceManifest(files=filenames,
                            data_schema=source_process_result.data_schema,
                            images=source_process_result.images)
  with open_file(os.path.join(output_dir, MANIFEST_FILENAME), 'w') as f:
    f.write(manifest.json(indent=2, exclude_none=True))
  log(f'Manifest for dataset "{dataset_name}" written to {output_dir}')

  return output_dir, source_process_result.num_items


@click.command()
@click.option('--output_dir',
              required=True,
              type=str,
              help='The output directory to write the parquet files to.')
@click.option('--config_path',
              required=True,
              type=str,
              help='The path to a json file describing the source configuration.')
@click.option('--dataset_name',
              required=True,
              type=str,
              help='The dataset name, used for binary mode only.')
@click.option('--namespace',
              required=False,
              default='local',
              type=str,
              help='The namespace to use. Defaults to "local".')
def main(output_dir: str, config_path: str, dataset_name: str, namespace: str) -> None:
  """Run the source loader as a binary."""
  register_default_sources()

  with open_file(config_path) as f:
    # Parse the json file in a dict.
    source_dict = json.load(f)
    source = resolve_source(source_dict)

  client = Client()
  client.submit(process_source, output_dir, namespace, dataset_name, source).result()


if __name__ == '__main__':
  main()
