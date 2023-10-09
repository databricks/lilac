# 🌸 Lilac

[![Static Badge](https://img.shields.io/badge/Homepage-8A2BE2?link=http%3A%2F%2Flilacml.com%2F)](https://lilacml.com)
[![Downloads](https://static.pepy.tech/badge/lilac/month)](https://pepy.tech/project/lilac)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Twitter](https://img.shields.io/twitter/follow/lilac_ai)](https://twitter.com/lilac_ai)
[![](https://dcbadge.vercel.app/api/server/jNzw9mC8pp?compact=true&style=flat)](https://discord.gg/jNzw9mC8pp)

> **NEW: Try the [Lilac hosted demo with pre-loaded datasets](https://lilacai-lilac.hf.space/)**

## 👋 Welcome

[Lilac](http://lilacml.com) is an open-source product that helps you **analyze**, **structure**, and
**clean** unstructured data with AI.

Lilac can be used from our UI or from Python.

https://github.com/lilacai/lilac/assets/2294279/cb1378f8-92c1-4f2a-9524-ce5ddd8e0c53

## 💻 Install

To install Lilac on your machine:

```sh
pip install lilac
```

You can also use Lilac with no installation by
[forking our public HuggingFace Spaces demo](https://lilacai-lilac.hf.space/).

## 🔥 Getting started

Start a Lilac webserver from the CLI:

```sh
lilac start ~/my_project
```

Or start the Lilac webserver from Python:

```py
import lilac as ll

ll.start_server(project_dir='~/my_project')
```

This will open start a webserver at http://localhost:5432/.

### Run via Docker

We haven't yet published a docker image, but you can build one locally:

```sh
docker build -t lilac .
```

The docker runs on the virtual port `8000`. If you have an existing lilac data direcotry you will
have to mount it and set the `LILAC_PROJECT_DIR` environment variable:

```sh
docker run -it \
  -p 8000:8000 \
  --volume /host/path/to/data:/data \
  -e LILAC_PROJECT_DIR="/data" \
  lilac
```

## 📁 Documentation

Visit our website: [lilacml.com](http://lilacml.com)

## 💻 Why Lilac?

Lilac is a visual tool and a Python API that helps you:

- **Explore** datasets with natural language (e.g. documents)
- **Enrich** your dataset with metadata (e.g. PII detection, profanity, text statistics, etc.)
- Conceptually **search** and tag your data (e.g. find paragraphs about injury)
- **Remove** unwanted or problematic data based on your own criteria
- **Analyze** patterns in your data

Lilac runs completely **on device** using powerful open-source LLM technologies.

## 💬 Contact

For bugs and feature requests, please
[file an issue on GitHub](https://github.com/lilacai/lilac/issues).

For general questions, please [visit our Discord](https://discord.com/invite/jNzw9mC8pp).
