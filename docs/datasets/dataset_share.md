# Sharing datasets

Datasets can also be shared by using HuggingFace datasets to upload / download Lilac formatted
datasets.

For example, the [lilac-glaive](https://huggingface.co/datasets/lilacai/lilac-glaive) dataset was
uploaded from a local project, and can be downloaded with the download CLI.

## From the CLI

### Upload

To upload a dataset from a local project:

```bash
lilac upload local/glaive --url_or_repo=lilacai/glaive
```

Optional arguments:

```
--project_dir: Specify a project directory. Defaults to env.LILAC_PROJECT_DIR.
--url_or_repo: Specify a url / repo to upload to. Defaults to 'lilac-{namespace}-{dataset_name}'.
--public: Make the dataset public. If private, the user downloading the dataset must have read
  access, and specify a huggingface token.
--readme_suffix: An additional suffix to add to the readme file of the dataset.
--hf_token: A huggingface access token, defaults to HF_ACCESS_TOKEN.
```

### Download

To download a dataset that was uploaded with the `lilac upload` command:

```bash
lilac download lilacai/glaive
```

Optional arguments:

```
--project_dir: Specify a project directory. Defaults to env.LILAC_PROJECT_DIR.
--dataset_namespace: A dataset namespace to use. Defaults to the namespace used on the uploaded
  dataset.
--dataset_name: A dataset name to use. Defaults to the name used on the uploaded dataset.
--hf_token: A huggingface access token, defaults to HF_ACCESS_TOKEN.
--overwrite: When true, overwrites any local dataset with the same namespace/name. When false,
  and a dataset with the same name exists, throws an error.
```

## From Python

The python APIs are the same as the CLI APIs above.

### Upload

To upload a dataset from Python:

```py
import lilac as ll

ll.upload('local/glaive', url_or_repo='lilacai/glaive')
```

For more details, see the API reference for [](#lilac.upload).

### Download

To download a dataset from Python:

```py
import lilac as ll

ll.download('lilacai/glaive')
```

For more details, see the API reference for [](#lilac.download).
