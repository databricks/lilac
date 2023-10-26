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

### Debug Lilac using pdb

To attach PDB to the Lilac server:

```sh
./run_server_pdb.sh
```

This starts the Lilac webserver in a single-threaded mode, ready to accept requests and respond to
PDB breakpoints. Pro-tip: Chrome's inspector can take logged network requests and Copy > Copy as
CURL command, which can be used to replay an API call to the Lilac server.

### Testing

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

These tests will all run on GitHub CI as well.

### Demos for PRs

We use HuggingFace spaces for demo links on PRs.
[Example](https://github.com/lilacai/lilac/pull/764).

1. Login with the HuggingFace to access git.

   `poetry run huggingface-cli login`

   [Follow the instructions](https://huggingface.co/docs/hub/repositories-getting-started) to use
   your git SSH keys to talk to HuggingFace.

1. Set `.env.local` environment variables so you can upload data to the space:

   ```sh
     # The repo to use for the huggingface demo. This does not have to exist when you set the flag, the deploy script will create it if it doesn't exist.
     HF_STAGING_DEMO_REPO='lilacai/your-space'
     # To authenticate with HuggingFace for uploading to the space.
     HF_ACCESS_TOKEN='hf_abcdefghijklmnop'
   ```

1. Deploy to your HuggingFace Space:

   ```
   poetry run python -m scripts.deploy_staging \
     --dataset=$DATASET_NAMESPACE/$DATASET_NAME

   # --create_space if this is the first time running the command so it will create the space for you.
   ```

### Publishing

#### Pip package

```sh
./scripts/publish_pip.sh
```

This will:

- Build the package (typescript bundle & python)
- Publish the package on pip and on github packages
- Build and publish the docker image
- Bump the version at HEAD
- Create release notes on GitHub

#### HuggingFace public demo

The HuggingFace public demo can be found [here](https://huggingface.co/spaces/lilacai/lilac).

To publish the demo:

```sh
poetry run python -m scripts.deploy_demo \
  --project_dir=./demo_data \
  --config=./lilac_hf_space.yml \
  --hf_space=lilacai/lilac

Add:
  --skip_sync to skip syncing data from the HuggingFace space data.
  --skip_load to skip loading the data.
  --load_overwrite to run all data from scratch, overwriting existing data.
  --skip_data_upload to skip uploading data. This will use the datasets already on the space.
  --skip_deploy to skip deploying to HuggingFace. Useful to test locally.
```

Typically, if we just want to push code changes without changing the data, run:

```sh
poetry run python -m scripts.deploy_demo \
  --project_dir=./demo_data \
  --config=./lilac_hf_space.yml \
  --hf_space=lilacai/lilac \
  --skip_sync \
  --skip_load \
  --skip_data_upload
```

The public demo uses the public pip package, so for code changes to land in the demo, they must
first be published on pip. This is so users that fork the demo will always get an updated Lilac.

#### Docker images

All docker images are published under the [lilacai](https://hub.docker.com/u/lilacai) account on
Docker Hub. We build docker images for two platforms `linux/amd64` and `linux/arm64`.

> NOTE: `./scripts/publish_pip.sh` will do this automatically.

##### Building on Google Cloud

```sh
gcloud builds submit \
  --config cloudbuild.yml \
  --substitutions=_VERSION=$(poetry version -s) \
  --async .
```

##### Building locally

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

### Configuration & Environment

To use various API's, API keys need to be provided. Create a file named `.env.local` in the root,
and add variables that are listed in `.env` with your own values.

The environment flags we use are listed in
[lilac/env.py](https://github.com/lilacai/lilac/blob/main/lilac/env.py).

### User Authentication for demos

End-user authentication is done via Google login, when `LILAC_AUTH_ENABLED` is set to true (e.g. in
the public HuggingFace demo where we disable features for most users).

A Google Client token should be created from the Google API Console. Details can be found
[here](https://developers.google.com/identity/protocols/oauth2).

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

### Installing poetry

You may need the following to install poetry:

- [Install XCode and sign license](https://apps.apple.com/us/app/xcode/id497799835?mt=12)
- [XCode command line tools](https://mac.install.guide/commandlinetools/4.html) (MacOS)
- [homebrew](https://brew.sh/) (MacOS)
- [pyenv](https://github.com/pyenv/pyenv) (Python version management)
- [Set your current python version](./.python-version)
- [Python Poetry](https://pypi.org/project/poetry/)
