```{tip}
Try the Lilac hosted **[demo on HuggingFace](https://lilacai-lilac.hf.space/)** or find us on GitHub: **[github.com/lilacai/lilac](https://github.com/lilacai/lilac)**
```

[![GitHub Repo stars](https://img.shields.io/github/stars/lilacai/lilac?logo=github&label=lilacai%2Flilac)](https://github.com/lilacai/lilac)
[![Downloads](https://static.pepy.tech/badge/lilac/month)](https://pepy.tech/project/lilac)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Twitter](https://img.shields.io/twitter/follow/lilac_ai)](https://twitter.com/lilac_ai)
[![](https://dcbadge.vercel.app/api/server/jNzw9mC8pp?compact=true&style=flat)](https://discord.gg/jNzw9mC8pp)

## 👋 Welcome

[Lilac](http://lilacml.com) is an open-source product that helps you **analyze**, **enrich**, and
**clean** unstructured data with AI.

See the [Installation](./getting_started/installation.md) and
[Quick Start](./getting_started/quickstart.md) guides to get started.

Read the [Announcement Blog](./blog/introducing-lilac.md) for more details.

<table style="border-spacing:0">
  <tr>
    <td style="width:200px;padding-right:10px;"><h4>Semantic and keyword search</h4></td>
    <td><video loop muted autoplay controls src="_static/welcome/semantic-search.mp4"></video></td>
  </tr>
</table>

<br/>
<br/>

<table style="border-spacing:0">
  <tr>
    <td><video loop muted autoplay controls src="_static/welcome/insights.mp4"></video></td>
    <td style="width:200px;padding-left:10px;"><h4>Dataset insights</h4></td>
  </tr>
</table>

<br/>
<br/>

<table style="border-spacing:0">
  <tr>
    <td style="width:200px;padding-left:10px;"><h4>PII, duplicates, language detection, or add your own signal</h4></td>
    <td><video loop muted autoplay controls src="_static/welcome/signals.mp4"></video></td>
  </tr>
</table>

<br/>
<br/>

<table style="border-spacing:0">
  <tr>
    <td><video loop muted autoplay controls src="_static/welcome/concepts.mp4"></video></td>
    <td style="width:200px;padding-left:10px;"><h4>Make your own concepts</h4></td>
  </tr>
</table>

<br/>
<br/>

<table style="border-spacing:0">
  <tr>
    <td style="width:200px;padding-left:10px;"><h4>Download the enriched data</h4></td>
    <td><video loop muted autoplay controls src="_static/welcome/download.mp4"></video></td>
  </tr>
</table>

## 💻 Install

To install Lilac on your machine:

```sh
pip install lilac
```

For more details see the [Installation](./getting_started/installation.md) guide. You can also use
Lilac with no installation by duplicating our public
[HuggingFace Spaces demo](https://lilacai-lilac.hf.space/).

## 🔥 Getting started

See the [Quick Start](./getting_started/quickstart.md) guide for an end-to-end example. To start the
Lilac webserver from the CLI:

```sh
lilac start ~/my_project
```

Or start the Lilac webserver from Python:

```py
import lilac as ll
ll.start_server(project_path='~/my_project')
```

This will start a webserver at http://localhost:5432/.

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
