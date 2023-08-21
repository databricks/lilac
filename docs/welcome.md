# 🌸 Lilac

![GitHub Repo stars](https://img.shields.io/github/stars/lilacai/lilac?logo=github&label=lilacai%2Flilac)
[![Downloads](https://static.pepy.tech/badge/lilacai/month)](https://pepy.tech/project/lilacai)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Twitter](https://img.shields.io/twitter/follow/lilac_ai)](https://twitter.com/lilac_ai)
[![](https://dcbadge.vercel.app/api/server/YpGxQMyk?compact=true&style=flat)](https://discord.gg/YpGxQMyk)

> **NEW: Try the [Lilac hosted demo with pre-loaded datasets](https://lilacai-lilac.hf.space/)**

## 👋 Welcome

[Lilac](http://lilacml.com) is an open-source product that helps you **analyze**, **structure**, and
**clean** unstructured data with AI.

Lilac can be used from our UI or from Python.

<video loop muted autoplay controls src="https://github-production-user-asset-6210df.s3.amazonaws.com/2294279/260771834-cb1378f8-92c1-4f2a-9524-ce5ddd8e0c53.mp4"></video>

## 💻 Install

To install Lilac on your machine:

```sh
pip install lilacai
```

You can also use Lilac with no installation by
[forking our public HuggingFace Spaces demo](https://lilacai-lilac.hf.space/).

## 🔥 Getting started

Start the Lilac webserver from the CLI:

```sh
lilac start
```

Or start the Lilac webserver from Python:

```py
import lilac as ll

ll.start_server()
```

This will open start a webserver at http://localhost:5432/.

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

For general questions, please [visit our Discord](https://discord.com/invite/YpGxQMyk).
