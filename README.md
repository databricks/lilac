# Lilac

### Prerequisites

Before you can run the server, install the following:

- [Python Poetry](https://pypi.org/project/poetry/)
- [NPM](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm)

### Install dependencies

```sh
./scripts/setup.sh
```

### Run Lilac

#### Development

To run the web server in dev mode with fast edit-refresh:

```sh
./run_server_dev.sh
```

Format typescript files:

```sh
npm run format --workspace web/lib
npm run format --workspace web/blueprint
```

##### Huggingface

Huggingface spaces are used for PRs and for demos.

Details can be found at [Managing Spaces with Github Actions](https://huggingface.co/docs/hub/spaces-github-actions)

We use the HuggingFace git server, [follow the instructions](https://huggingface.co/docs/hub/repositories-getting-started) to use your git SSH keys to talk to HuggingFace.

To deploy to huggingface:

```
poetry run python -m scripts.deploy_hf \
  --hf_username=$HF_USERNAME \
  --hf_space=$HF_ORG/$HF_SPACE \
  --dataset=$DATASET_NAMESPACE/$DATASET_NAME
```

#### Deployment

To build the docker image:

```sh
./build_docker.sh
```

To run the docker image locally:

```sh
docker run -p 5432:5432 lilac_blueprint
```

### Configuration

To use various API's, API keys need to be provided. Create a file named `.env.local` in the root, and add variables that are listed in `.env` with your own values.

#### Testing

Run all the checks before mailing:

```sh
./scripts/checks.sh
```

Test python:

```sh
./scripts/test_py.sh
```

Test JavaScript:

```sh
./scripts/test_ts.sh
```

### Ingesting datasets from CLI

Datasets can be ingested entirely from the UI, however if you prefer to use the CLI you can ingest data with the following command:

```sh
poetry run python -m src.data_loader \
  --dataset_name=$DATASET \
  --output_dir=./data/ \
  --config_path=./datasets/the_movies_dataset.json
```

NOTE: You have to have a JSON file that represents your sour configuration, in this case
"the_movies_dataset.json".

### Tips

#### Recommended dev tools

- [VSCode](https://code.visualstudio.com/)

#### Installing poetry

You may need the following to install poetry:

- [Install XCode and sign license](https://apps.apple.com/us/app/xcode/id497799835?mt=12)
- [XCode command line tools](https://mac.install.guide/commandlinetools/4.html) (MacOS)
- [homebrew](https://brew.sh/) (MacOS)
- [pyenv](https://github.com/pyenv/pyenv) (Python version management)
- [Set your current python version](./.python-version)
- [Python Poetry](https://pypi.org/project/poetry/)

### Troubleshooting

#### pyenv install not working on M1

If your pyenv does not work on M1 machines after installing xcode, you may need to reinstall xcode command line tools. [Stack Overflow Link](https://stackoverflow.com/questions/65778888/pyenv-configure-error-c-compiler-cannot-create-executables)

#### No module named `_lzma`

Follow instructions from [pyenv](https://github.com/pyenv/pyenv/wiki#suggested-build-environment):

- Uninstall python via `pyenv uninstall`
- Run `brew install openssl readline sqlite3 xz zlib tcl-tk`
- Reinstall python via `pyenv install`

```sh
$ sudo rm -rf /Library/Developer/CommandLineTools
$ xcode-select --install
```

#### Installing TensorFlow on M1

M1/M2 chips need a special TF installation. These steps are taken from the official
[Apple docs](https://developer.apple.com/metal/tensorflow-plugin/):

1. Click [here](https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-MacOSX-arm64.sh) to download Conda env
2. Run:

```
chmod +x ~/Downloads/Miniforge3-MacOSX-arm64.sh
sh ~/Downloads/Miniforge3-MacOSX-arm64.sh
source ~/miniforge3/bin/activate
```

3. Install the TensorFlow `2.9.0` dependencies: `conda install -c apple tensorflow-deps=2.9.0`

#### Too many open files on MacOS

When downloading and pre-processing TFDS datasets, you might get `too many open files`
error. To fix, increase [the max open files limit](https://superuser.com/a/1679740).
