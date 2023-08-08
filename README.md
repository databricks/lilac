# Lilac 🌸

Analyze, structure and clean unstructured data with AI.

[![Downloads](https://static.pepy.tech/badge/lilacai/month)](https://pepy.tech/project/lilacai)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Twitter](https://img.shields.io/twitter/follow/lilac_ai)](https://twitter.com/lilac_ai)
[![](https://dcbadge.vercel.app/api/server/Mq7AGrmv?compact=true&style=flat)](https://discord.gg/Mq7AGrmv)
[![Dev Container](https://img.shields.io/static/v1?label=Dev%20Containers&message=Open&color=blue&logo=visualstudiocode)](https://vscode.dev/redirect?url=vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https://github.com/lilacai/lilac)
[![GitHub Codespace](https://github.com/codespaces/badge.svg)](https://codespaces.new/lilacai/lilac)

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

###### Staging demo

1. Login with the HuggingFace to access git.

   `poetry run huggingface-cli login`

   [Follow the instructions](https://huggingface.co/docs/hub/repositories-getting-started) to use your git SSH keys to talk to HuggingFace.

1. Create a huggingface space from your browser: [huggingface.co/spaces](https://huggingface.co/spaces)

1. Turn on persistent storage in the Settings UI.

1. Set .env.local environment variables so you can upload data to the space:

   ```sh
     # The repo to use for the huggingface demo.
     HF_STAGING_DEMO_REPO='lilacai/your-space'
     # To authenticate with HuggingFace for uploading to the space.
     HF_USERNAME='your-username'
   ```

1. Deploy to your HuggingFace Space:

   ```
   poetry run python -m scripts.deploy_hf \
     --dataset=$DATASET_NAMESPACE/$DATASET_NAME

   # --concept is optional. By default all lilac/* concepts are uploaded. This flag enables uploading other concepts from local.
   # --hf_username and --hf_space are optional and can override the ENV for local uploading.
   ```

#### Deployment

To build the docker image:

```sh
./scripts/build_docker.sh
```

To run the docker image locally:

```sh
docker run -p 5432:5432 lilac_blueprint
```

#### Authentication

Authentication is done via Google login. A Google Client token should be created
from the Google API Console. Details can be found [here](https://developers.google.com/identity/protocols/oauth2).

By default, the Lilac google client is used. The secret can be found in Google
Cloud console, and should be defined under `GOOGLE_CLIENT_SECRET` in .env.local.

For the session middleware, a random string should be created and defined as `LILAC_OAUTH_SECRET_KEY` in .env.local.

You can generate a random secret key with:

```py
import string
import random
key = ''.join(random.choices(string.ascii_uppercase + string.digits, k=64))
print(f"LILAC_OAUTH_SECRET_KEY='{key}'")
```

### Publishing on pip

To authenticate, add the `PYPI_TOKEN` to your `.env.local` file. You can get the token from
[pypi.org](https://pypi.org/manage/project/lilacai/settings/). To publish, run:

```sh
./scripts/publish_pip.sh
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
poetry run lilac load \
  --output_dir=demo_data \
  --config_path=demo.yml
```

NOTE: You must have a config JSON or YAML file that represents your dataset configuration. The config
should be an instance of the pydantic class `lilac.Config` (for multiple datasets) or
`lilac.DatasetConfig` (for a single dataset).

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
