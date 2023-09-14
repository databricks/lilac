# Load a dataset

```{tip}
[Explore popular datasets in Lilac on HuggingFace](https://lilacai-lilac.hf.space/)
```

Loading a dataset can be done from the UI or from Python. See [](#lilac.sources) for details on
available sources.

## From the UI

### Start the webserver

To start the webserver at a lilac project directory:

```sh
lilac start ~/my_project
```

This will start an empty lilac project under `~/my_project`, with an empty `lilac.yml` and start the
webserver. The configuration for `lilac.yml` can be found at [](#Config). The `lilac.yml` file will
stay up to date with interactions from the UI. This can be manually edited, or just changed via the
UI. For more information on peojcts, see [Projects](../projects/projects.md).

### Load a dataset

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

### Loading from lilac.yml

When you start a webserver, Lilac will automatically create a project for you in the given project
path, with an empty `lilac.yml` file in the root of the project directory. See
[Projects](../projects/projects.md) for more information.

```python
import lilac as ll

ll.start_server(project_dir='~/my_lilac')
```

This will create a project file:

```sh
~/my_lilac/lilac.yml
```

The configuration for `lilac.yml` can be found at [](#Config). The `lilac.yml` file will stay up to
date with commands from python, however this file can also be manually edited.

The next time the web server boots up, the `lilac.yml` file will be read and loaded. Tasks will be
visible from the UI.

Alternatively, you can explicitly load the lilac.yml after editing it without starting the
webserver:

```python
ll.load(project_dir='~/my_lilac')
```

Or from the CLI:

```sh
lilac load --project_dir=~/my_lilac
```

### Loading an individual dataset

This example loads the `glue` dataset with the `ax` config from HuggingFace:

```python
# Set the global project directory to where project files will be stored.
ll.set_project_dir('~/my_project')

config = ll.DatasetConfig(
  namespace='local',
  name='glue',
  source=ll.HuggingFaceSource(dataset_name='glue', config_name='ax'))

# NOTE: If you don't want to set a global project directory, you can pass the `project_dir` to `create_dataset` as the second argument.
dataset = ll.create_dataset(config)
```

For details on all the source loaders, see [](#lilac.sources).

For details on the dataset config, see [](#lilac.DatasetConfig).
