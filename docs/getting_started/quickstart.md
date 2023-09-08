# Quick Start

```{tip}
Make sure you've followed the [installation](installation.md) steps first.
```

```{note}
For a Python-based quick start, see [Quick Start (Python)](./quickstart_python.md).
```

## Overview

In this quick start we're going to:

- Load [OpenOrca](https://huggingface.co/datasets/Open-Orca/OpenOrca), a popular instruction dataset
  for tuning LLMs.
- Find PII (emails, etc)
- Find profanity in the responses (using powerful text embeddings)
- Download the enriched dataset as a json file so we can clean it in a Python notebook

## Start the web server

Start a new Lilac project.

```bash
lilac start ~/my_project
```

This should open a browser tab pointing to [http://localhost:5432](http://localhost:5432).

## Add a dataset

Let's load [OpenOrca](https://huggingface.co/datasets/Open-Orca/OpenOrca), a popular instruction
dataset used for tuning LLM models.

Click the `Add dataset` button on the Getting Started page and fill in:

1. The dataset name in the Lilac project: `open-orca-10k`
2. Choose `huggingface` dataset loader chechbox

Fill in HuggingFace-specific fields:

3. HuggingFace dataset name: `Open-Orca/OpenOrca`
4. Sample size: 10000 (it takes ~5mins to compute on-device embeddings for 10,000 items)

Finally:

5. Click the "Add" button at the bottom.

```{note}
See the console output to track progress of the dataset download from HuggingFace.
```

<video loop muted autoplay controls src="../_static/getting_started/orca-load.mp4"></video>

## Configure

When we load a dataset, Lilac creates a default UI configuration, inferring which fields are _media_
(e.g. unstructured documents), and which are _metadata_ fields. The two types of fields are
presented differently in the UI.

Let's edit the configuration by clicking the `Dataset settings` button in the top-right corner. If
your media field contains markdown, you can enable markdown rendering.

<video loop muted autoplay controls src="../_static/getting_started/orca-settings.mp4"></video>

## Enrich

Lilac can enrich your media fields with additional metadata by:

- Running a [signal](../signals/signals.md) (e.g. PII detection, language detection, text
  statistics, etc.)
- Running a [concept](../concepts/concepts.md) (e.g. profanity, sentiment, etc. or a custom concept
  that you create)

### PII detection

Let's run the PII detection signal on both the `question` and the `response` field and see if there
is any PII like emails, secret tokens, etc.

<video loop muted autoplay controls src="../_static/getting_started/orca-pii-enrichment.mp4"></video>

Once it's done, we can see that both the `question` and the `response` fields have emails present.
We can click on an email to apply a filter and see all the rows that contain that email.

<video loop muted autoplay controls src="../_static/getting_started/orca-pii-filter.mp4"></video>

We notice that the selected email in the `response` field was not hallucinated by the LLM because it
was also present in the `question` field. Later we can use the enriched metadata of both fields to
filter out only responses that have hallucinated emails.

### Profanity detection

Let's also run the profanity concept on the `response` field to see if the LLM produced any profane
content. To see the results, we need to _index_ the `response` field using a text embedding. We only
need to index once. For a fast on-device embedding, we recommend the
[GTE-Small embedding](https://huggingface.co/thenlper/gte-small).

<video loop muted autoplay controls src="../_static/getting_started/orca-index-response.mp4"></video>

It takes ~20 minutes to index the 100,000 responses on a Macbook M1. Now that the field is indexed,
we can now do _semantic search_ and _concept search_ on the field (in addition to the usual _keyword
search_).

Let's search by the profanity concept and see if the LLM produced any profane content. Results in
the video are blurred due to sensitive content.

Concepts by default run in _preview_ mode, where we only compute the concept scores for the top K
results. To compute the concept score over the entire dataset, we click the blue `Compute signal`
button next to `lilac/profanity/gte-small` in the schema.

<video loop muted autoplay controls src="../_static/getting_started/orca-profanity-preview.mp4"></video>

Computing the concept takes ~20 seconds on a Macbook M1 laptop. Now that the concept is computed, we
can open the statistics panel to see the distribution of concept scores.

<video loop muted autoplay controls src="../_static/getting_started/orca-profanity-stats.mp4"></video>

## Download

Now that we've enriched the dataset, let's download it by clicking on the `Download data` button in
the top-right corner. This will download a json file with the same name as the dataset. Once we have
the data, we can continue working with it in a Python notebook, or any other language.

For other formats (csv, parquet, pandas, etc.) see the
[Download section](quickstart_python.md#download) in [Quick Start (Python)](quickstart_python.md).

<video loop muted autoplay controls src="../_static/getting_started/orca-download.mp4"></video>
