# Projects

Lilac projects are a way to organize your datasets and concepts into separate directories.

Project configurations are a way to specify which datasets, signals and concepts to run to create a
Lilac instance.

An example project directory:

```sh
~/my_project
    lilac.yml
    datasets/
        open-orca/
    concept/
```

## Project directory

When starting the webserver from the CLI or from Python, a project directory will be created for you
implicitly when passing `project_dir`.

From CLI:

```sh
lilac start ~/my_project
```

From Python:

```python
import lilac as ll

ll.start_server(project_dir='~/my_project')
```

In both cases, if `~/my_project` doesn't exist, a directory will be created with an empty project
configuration:

```yml
# Lilac project config.
# See https://lilacml.com/api_reference/index.html#lilac.Config for details.

datasets: []
```

If you want to start a Lilac project without starting a webserver, you can use [](#init).

From CLI:

```sh
lilac init ~/my_project
```

From Python:

```python
import lilac as ll

ll.init(project_dir='~/my_project')
```

### Setting the project directory globally

If we don't want to pass the `project_dir` around, we can set the project dir globally by using the
[](#LilacEnvironment.LILAC_PROJECT_DIR) environment flag, or the python API [](#set_project_dir).

```bash
export LILAC_PROJECT_DIR='~/my_project'
```

Python:

```python
import lilac as ll

# This will set the `LILAC_PROJECT_DIR` environment flag globally. Any future calls to Lilac will use this project directory.
ll.set_project_dir('~/my_project')
```

## Configuration

The `lilac.yml` file in the root of the project directory is a yaml instance of [](#Config).

An example configuration:

```yml
# Lilac project config.
# See https://lilacml.com/api_reference/index.html#lilac.Config for details.

datasets:
  - namespace: local
    name: glue
    source:
      dataset_name: glue
      config_name: ax
      source_name: huggingface
    embeddings:
      - path: premise
        embedding: gte-small
    signals:
      - path: premise
        signal:
          signal_name: pii
      - path: hypothesis
        signal:
          signal_name: pii
    settings:
      ui:
        media_paths:
          - premise
```

Let's break the configuration down. The first thing you'll see is the datasets configuration, which
is an array of [](#DatasetConfig).

Here we have one dataset with namespace `local` and name `glue`.

```yaml
datasets:
  - namespace: local
    name: glue
```

The next section defines the data source, this case we're reading the
[`glue`](https://huggingface.co/datasets/glue) dataset from HuggingFace with the `ax` configuration:

```yaml
source:
  dataset_name: glue
  config_name: ax
  source_name: huggingface
```

The next section will define the [embeddings](../embeddings/embeddings.md) to be computed on certain
fields. Here we're computing the `gte-small` embedding over the `premise` field:

```yaml
embeddings:
  - path: premise
    embedding: gte-small
```

The next section defines the [signals](../signals/signals.md) to be computed on certain fields. Here
we're computing `pii` over `premise` and also over `hypothesis`.

```yaml
signals:
  - path: premise
    signal:
      signal_name: pii
  - path: hypothesis
    signal:
      signal_name: pii
```

The last section defines the dataset settings. This configuration sets the `premise` as the only
media path to be shown in the UI. The media path is what renders in the larger section of the UI, as
a larger text field.

```yaml
settings:
  ui:
    media_paths:
      - premise
```
