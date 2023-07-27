# Installation

Lilac is published on pip under [lilacai](https://pypi.org/project/lilacai/). You can install it with:

```bash
pip install lilacai
```

To make sure the installation works, start the web server:

```bash
lilac start
```

To check the version:

```bash
lilac version
```

## Environment setup

To use hosted services for computing embeddings, add the following environment variables:

- `OPENAI_API_KEY`: OpenAI API key. You can get one [here](https://platform.openai.com/account/api-keys).
- `COHERE_API_KEY`: Cohere API key. You can get one [here](https://dashboard.cohere.ai/api-keys).
- `PALM_API_KEY`: PaLM API key. You can get one [here](https://makersuite.google.com/app/apikey).
