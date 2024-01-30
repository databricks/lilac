# Installation

## PIP

Lilac is published on pip under [lilac](https://pypi.org/project/lilac/). You can install it with:

```bash
pip install lilac[all]
```

```{note}
To skip optional dependencies, run `pip install lilac` instead. You will have to manually install
any dependencies. For example to install GTE embedding, do `pip install lilac[gte]`.
```

## Docker

### Docker Hub

We publish images for `linux/amd64` and `linux/arm64` on Docker Hub under
[lilacai](https://hub.docker.com/u/lilacai).

The container runs on the virtual port `80`, this command maps it to the host machine port `5432`.

If you have an existing lilac project, mount it and set the `LILAC_PROJECT_DIR` environment
variable:

```sh
docker run -it \
  -p 5432:80 \
  --volume /host/path/to/data:/data \
  -e LILAC_PROJECT_DIR="/data" \
  --gpus all \ # Remove if you don't have a GPU, or on MacOS.
  lilacai/lilac
```

### Your own image

To build your own custom image, fork our [Dockerfile](../../Dockerfile), or build it from the root
of the repository:

```sh
docker build -t lilac .
```

## Test the installation

To make sure the installation works, start a new lilac project:

```{note}
If this is a fresh virtual env, it might take a dozen seconds to see the initial output.
```

```bash
❯ lilac start ~/my_project
Lilac will create a project in `/Users/me/my-project`. Do you want to continue? (y/n): y

INFO:     Started server process [33100]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:5432 (Press CTRL+C to quit)
```

This should start a web server at [http://localhost:5432](http://localhost:5432).

To check the current version:

```bash
lilac version
```

## Environment setup

To use hosted services for computing embeddings, add the following environment variables:

- `OPENAI_API_KEY`: OpenAI API key. You can get one
  [here](https://platform.openai.com/account/api-keys).
- `COHERE_API_KEY`: Cohere API key. You can get one [here](https://dashboard.cohere.ai/api-keys).
