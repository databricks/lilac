```{tip}
Try the Lilac hosted **[demo on HuggingFace](https://huggingface.co/spaces/lilacai/lilac)** or find
us on GitHub: **[github.com/lilacai/lilac](https://github.com/lilacai/lilac)**
```

# Introducing Lilac

August 21, 2023 <br/> _Daniel Smilkov & Nikhil Thorat_

Lilac is an **open-source** tool that enables AI practitioners to see and quantify their datasets.

For an end-to-end example, see our [Quick Start](../getting_started/quickstart.md) guide.

For a detailed documentation, [visit our website](https://lilacml.com/).

<video loop muted autoplay controls src="https://github-production-user-asset-6210df.s3.amazonaws.com/2294279/260771834-cb1378f8-92c1-4f2a-9524-ce5ddd8e0c53.mp4"></video>

Lilac allows users to:

- Browse datasets with unstructured data.
- Enrich unstructured fields with structured metadata using
  [Lilac Signals](https://lilacml.com/signals/signals.html), for instance **near-duplicate** and
  **personal information detection**. Structured metadata allows us to compute statistics, find
  problematic slices, and eventually measure _changes_ over time.
- Create and refine **[Lilac Concepts](https://lilacml.com/concepts/concepts.html)** which are
  customizable AI models that can be used to find and score text that matches a concept you may have
  in your mind.
- Download the results of the enrichment for downstream applications.

Out of the box, Lilac comes with a set of generally useful **Signals** and **Concepts**, however
this list is not exhaustive and we will continue to work with the OSS community to continue to add
more useful enrichments.

### Our mission

At Lilac, our mission is to make unstructured data **visible**, **quantifiable**, and **malleable**.

This will lead to:

- Higher quality AI models
- Better actionability when AI models fail
- Better control and visibility of model bias

### Data quality in AI is tricky

During our time at Google, we collaborated with many teams to improve datasets used to build their
AI models. Their goal was to continually improve the quality of their models, often focusing on
refining the training data.

What makes improving data quality difficult is that many AI models rely on **unstructured data**,
such as natural language or images, that lack any labels or useful metadata. To complicate matters,
what constitutes “good” data depends heavily on the application and the user experience. Despite
these differences, a common thread emerged: while teams would compute aggregate statistics to
understand the general composition of their data, they often overlooked the raw data. When
methodically organized and visualized, glaring bugs in datasets would present themselves, often with
simple fixes leading to higher quality models.

### "Bad data"

"Bad data" is often hard to define, but we often know bad data when we see it. In other cases, “bad
data" isn’t objectively bad: for instance, the presence of German text in a French to English
translation dataset will negatively affect the translation model, even if the translation is correct
for German.

With that observation in mind, at Google we built tools and processes that empowered teams to
**see** their data. To summarize a few years of learning into one sentence: each dataset has its own
quirks, and these quirks can have non-obvious implications for the quality of downstream models.

Today, data cleaning for datasets fed into AI models is often done with heuristics in a Python
script, with little visibility into the side effects of that change.

### Concepts

Since each AI application has its own requirements, we’re focused on enabling users to annotate data
with customizable **[Concepts](https://lilacml.com/concepts/concepts.html)**. Concepts can be
created and refined through the UI, and updated in real-time with user-feedback. These AI-powered
embedding-based classifiers can be specific to an application, e.g. **termination clauses in legal
contracts**, or generally applicable, e.g. **toxicity**.

### On-device

Data privacy is an important consideration for most AI teams, so we are focused on making Lilac fast
and usable with data staying on-premise. Lilac Concepts utilize powerful on-device embeddings, like
[GTE](https://huggingface.co/thenlper/gte-small). However if your application is not sensitive to
data privacy (e.g. using open-source datasets), you may choose to use more powerful embeddings like
[OpenAI](https://platform.openai.com/docs/guides/embeddings),
[Cohere](https://docs.cohere.com/docs/embeddings), [PaLM](https://developers.generativeai.google/),
or your own! For more information on embeddings,
[see our documentation](https://lilacml.com/embeddings/embeddings.html).

### HuggingFace demo

We are also hosting a [HuggingFace space](https://huggingface.co/spaces/lilacai/lilac) with a
handful of popular datasets (e.g. [OpenOrca](https://huggingface.co/datasets/Open-Orca/OpenOrca))
and curated concepts (e.g. [profanity](https://lilacai-lilac.hf.space/concepts#lilac/profanity),
[legal termination](https://lilacai-lilac.hf.space/concepts#lilac/legal-termination),
[source-code detection](https://lilacai-lilac.hf.space/concepts#lilac/source-code), etc.). In this
demo, you can browse pre-enriched datasets and even create your own concepts. The space can be
forked and made private with your own data, skipping the installation process of Lilac.

### Open source

We believe an open-source product is the best way to improve the culture around dataset quality.

We encourage the AI community to try the tool and help us grow a central repository of useful
concepts and signals. We would love to collaborate to shed light on the most popular AI datasets.

Let’s visualize, quantify, and ultimately improve all unstructured datasets.
