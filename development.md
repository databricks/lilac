## Development

### Setup

Before you can run the server, install the following:

- [Python Poetry](https://pypi.org/project/poetry/)
- [NPM](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm)

### Install dependencies

```sh
./scripts/setup.sh
```

### Run Lilac in dev mode

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

Details can be found at
[Managing Spaces with Github Actions](https://huggingface.co/docs/hub/spaces-github-actions)

###### Staging demo

1. Login with the HuggingFace to access git.

   `poetry run huggingface-cli login`

   [Follow the instructions](https://huggingface.co/docs/hub/repositories-getting-started) to use
   your git SSH keys to talk to HuggingFace.

1. Create a huggingface space from your browser:
   [huggingface.co/spaces](https://huggingface.co/spaces)

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
   poetry run python -m scripts.deploy_staging \
     --dataset=$DATASET_NAMESPACE/$DATASET_NAME

   # --concept is optional. By default all lilac/* concepts are uploaded. This flag enables uploading other concepts from local.
   # --hf_username and --hf_space are optional and can override the ENV for local uploading.
   ```

#### Publishing docker images

All docker images are published under the [lilacai](https://hub.docker.com/u/lilacai) account on
Docker Hub. We build docker images for two platforms `linux/amd64` and `linux/arm64`.

> NOTE: `./scripts/publish_pip.sh` will do this automatically.

**Building on Google Cloud**

```sh
gcloud builds submit \
  --config cloudbuild.yml \
  --substitutions=_VERSION=$(poetry version -s) \
  --async .
```

**Building locally**

To build the image for both platforms, as a one time setup do:

```sh
docker buildx create --name mybuilder --node mybuilder0 --bootstrap --use
```

Make sure you have Docker Desktop running and you are logged as the lilacai account. To build and
push the image:

```sh
docker buildx build --platform linux/amd64,linux/arm64 \
  -t lilacai/lilac \
  -t lilacai/lilac:$(poetry version -s) \
  --push .
```

#### Authentication

Authentication is done via Google login. A Google Client token should be created from the Google API
Console. Details can be found [here](https://developers.google.com/identity/protocols/oauth2).

By default, the Lilac google client is used. The secret can be found in Google Cloud console, and
should be defined under `GOOGLE_CLIENT_SECRET` in .env.local.

For the session middleware, a random string should be created and defined as
`LILAC_OAUTH_SECRET_KEY` in .env.local.

You can generate a random secret key with:

```py
import string
import random
key = ''.join(random.choices(string.ascii_uppercase + string.digits, k=64))
print(f"LILAC_OAUTH_SECRET_KEY='{key}'")
```

### Publishing on pip

To authenticate, add the `PYPI_TOKEN` to your `.env.local` file. You can get the token from
[pypi.org](https://pypi.org/manage/project/lilac/settings/). To publish, run:

```sh
./scripts/publish_pip.sh
```

### Configuration

To use various API's, API keys need to be provided. Create a file named `.env.local` in the root,
and add variables that are listed in `.env` with your own values.

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

Datasets can be ingested entirely from the UI, however if you prefer to use the CLI you can ingest
data with the following command:

```sh
poetry run lilac load \
  --project_dir=demo_data \
  --config_path=demo.yml
```

NOTE: You must have a config JSON or YAML file that represents your dataset configuration. The
config should be an instance of the pydantic class `lilac.Config` (for multiple datasets) or
`lilac.DatasetConfig` (for a single dataset).

### Installing poetry

You may need the following to install poetry:

- [Install XCode and sign license](https://apps.apple.com/us/app/xcode/id497799835?mt=12)
- [XCode command line tools](https://mac.install.guide/commandlinetools/4.html) (MacOS)
- [homebrew](https://brew.sh/) (MacOS)
- [pyenv](https://github.com/pyenv/pyenv) (Python version management)
- [Set your current python version](./.python-version)
- [Python Poetry](https://pypi.org/project/poetry/)
