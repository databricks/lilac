# Quick Start (Python)

```{tip}
Make sure you've followed the [installation](installation.md) steps first.
```

## Overview

In this quick start we're going to:

- Load [OpenOrca](https://huggingface.co/datasets/Open-Orca/OpenOrca), a popular instruction dataset
  for tuning LLMs.
- Find PII (emails, etc)
- Find profanity in the responses (using powerful text embeddings)
- Download the enriched dataset as a json file so we can clean it in a Python notebook

## Add a dataset

```python
import lilac as ll

source = ll.HuggingFaceDataset(dataset_name='Open-Orca/OpenOrca', sample_size=100_000)
config = ll.DatasetConfig(namespace='local', name='open-orca-100k', source=source)
dataset = ll.create_dataset(config)
```

```sh
Downloading data files: 100%|██████████████████████████████████████| 1/1 [05:14<00:00, 314.85s/it]
Extracting data files: 100%|███████████████████████████████████████| 1/1 [00:00<00:00, 318.98it/s]
Setting num_proc from 8 to 2 for the train split as it only contains 2 shards.
Generating train split: 4233923 examples [00:06, 654274.93 examples/s]
Reading from source huggingface...: 100%|██████████████| 100000/100000 [00:03<00:00, 30124.10it/s]
Dataset "open-orca-100k" written to ./data/datasets/local/open-orca-100k
```

## Enrich

Lilac can enrich your media fields with additional metadata by:

- Running a [signal](../signals/signals.md) (e.g. PII detection, language detection, text
  statistics, etc.)
- Running a [concept](../concepts/concepts.md) (e.g. profanity, sentiment, etc. or a custom concept
  that you create)

### PII detection

To keep the binary pip package small, we don't include the optional dependencies for signals like
PII detection. To install the optional pii, run:

```sh
pip install lilacai[pii]
```

Let's run the PII detection signal on both the `question` and the `response` field.

```python
dataset = ll.get_dataset('local', 'open-orca-100k')
dataset.compute_signal(ll.PIISignal(), 'question')
dataset.compute_signal(ll.PIISignal(), 'response')
```

```sh
Computing pii on local/open-orca-100k:question: 100%|█████████████████████████████████████| 100000/100000 [03:36<00:00, 462.62it/s]
Computing signal "pii" on local/open-orca-100k:question took 216.246s.
Wrote signal output to ./data/datasets/local/open-orca-100k/question/pii
Computing pii on local/open-orca-100k:response: 100%|█████████████████████████████████████| 100000/100000 [02:21<00:00, 708.04it/s]
Computing signal "pii" on local/open-orca-100k:response took 141.312s.
Wrote signal output to ./data/datasets/local/open-orca-100k/response/pii
```

The dataset now has extra fields for each of the computed signal:

```py
print(dataset.select_rows(limit=5).df())
```

```sh
             id                                      system_prompt                                           question  ...                         __rowid__                                       question.pii                                       response.pii
0    flan.77076  You are an AI assistant. User will you give yo...  How does the sentence end?\n\n(CNN) -- When sh...  ...  91885e6e7ff7490687fc3cd23e43eb3f  {'emails': [], 'ip_addresses': [], 'secrets': []}  {'emails': [], 'ip_addresses': [], 'secrets': []}
1     t0.666355  You are an AI assistant that follows instructi...  Question: Formulate an answer to this elaborat...  ...  c465f6be84eb4d7e8eb6a65f9aa69b57  {'emails': [], 'ip_addresses': [], 'secrets': []}  {'emails': [], 'ip_addresses': [], 'secrets': []}
2  flan.1931582  You are an AI assistant. You should describe t...  Gee willickers , Katie has a LOT of stuff ! It...  ...  d7aed78ea5dd497e83abd966160d00ac  {'emails': [], 'ip_addresses': [], 'secrets': []}  {'emails': [], 'ip_addresses': [], 'secrets': []}
3     t0.885030  You are an AI assistant. Provide a detailed an...  - death place is leiden , netherlands    - fie...  ...  711ca0f29d044dadb587ad4fcf1d4798  {'emails': [], 'ip_addresses': [], 'secrets': []}  {'emails': [], 'ip_addresses': [], 'secrets': []}
4  flan.1503589  You are a helpful assistant, who always provid...  The firemen arrived before the police because ...  ...  3909dc8dbafe43e2b8a60fb91e763cf2  {'emails': [], 'ip_addresses': [], 'secrets': []}  {'emails': [], 'ip_addresses': [], 'secrets': []}

[5 rows x 8 columns]
```

### Profanity detection

Let's also run the profanity concept on the `response` field to see if the LLM produced any profane
content. To see the results, we need to _index_ the `response` field using a text embedding. We only
need to index once. For a fast on-device embedding, we recommend the
[GTE-Small embedding](https://huggingface.co/thenlper/gte-small).

Before we can index with GTE-small, we need to install the optional dependencies:

```sh
pip install sentence-transformers
```

```py
dataset.compute_embedding('gte-small', 'response')
```

```sh
Computing gte-small on local/open-orca-100k:('response',):   2%|████              | 2473/100000 [00:54<34:25, 47.22it/s]
```

Now we can preview the top 5 responses based on their profanity concept score:

```py
query = ll.ConceptQuery(concept_namespace='lilac', concept_name='profanity', embedding='gte-small')
r = dataset.select_rows(['overview'], searches=[ll.Search(path='overview', query=query)], limit=5)
print(r.df())
```

TODO: Fix concept not found.

To compute the concept score over the entire dataset, we do:

```py
dataset.compute_signal(
    ll.ConceptScoreSignal(namespace='lilac',
                          concept_name='profanity',
                          embedding='gte-small'), 'response')
```

TODO: Fix concept not found.

## Download

TODO
