# Load a dataset

```{tip}
[Explore popular datasets in Lilac on HuggingFace](https://huggingface.co/spaces/lilacai/lilac)
```

Loading a dataset can be done from the UI or from Python. See [](#lilac.sources) for details on
available sources.

## From the UI

To load a dataset from the UI, click the "Add dataset" button from the "Getting Started" homepage.

<img src="../_static/dataset/dataset_getting_started.png"></img>

This will open the dataset loader UI:

<img src="../_static/dataset/dataset_load.png"></img>

##### Step 1: Name your dataset

- `namespace`: The dataset namespace group. This is useful for organizing dataset into categories,
  or organizations.
- `name`: The name of the dataset within the namespace.

##### Step 2: Chose a source (data loader)

- [`csv`](#lilac.sources.CSVSource): Load from CSV files.
- [`huggingface`](#lilac.sources.HuggingFaceSource): Load from a HuggingFace dataset.
- [`json`](#lilac.sources.JSONSource): Load JSON or JSONL files.
- [`gmail`](#lilac.sources.GmailSource): Load your emails from gmail. No data is sent to an external
  server, unless you use a remote embedding. See [Embeddings](../embeddings/embeddings.md) on
  chosing an embedding.
- [`parquet`](#lilac.sources.ParquetSource): Load from parquet files.

More details on the available data loaders can be found in [](#lilac.sources).

Don't see a data loader? File a bug, or send a PR to
[https://github.com/lilacai/lilac](https://github.com/lilacai/lilac)!

##### Step 3: Load your data!

After you click "Add", a task will be created:

<img src="../_static/dataset/dataset_load_tasks.png"></img>

You will be redirected to the dataset view once your data is loaded.

## From Python

This example loads the `glue` dataset with the `ax` config from HuggingFace:

```python
config = ll.DatasetConfig(
  namespace='local',
  name='glue',
  source=ll.HuggingFaceSource(dataset_name='glue', config_name='ax'))
dataset = ll.create_dataset(config)
```

For details on all the source loaders, see [](#lilac.sources).

For details on the dataset config, see [](#lilac.DatasetConfig).
