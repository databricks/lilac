# Installation

Lilac is published on pip under [lilac](https://pypi.org/project/lilac/). You can install it with:

```bash
pip install lilac[all]
```

```{note}
To skip optional dependencies, run `pip install lilac` instead. You will have to manually install any
dependencies. For example to install GTE embedding, do `pip install lilac[gte]`.
```

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
- `PALM_API_KEY`: PaLM API key. You can get one [here](https://makersuite.google.com/app/apikey).
