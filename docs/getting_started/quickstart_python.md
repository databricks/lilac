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

Let's load [OpenOrca](https://huggingface.co/datasets/Open-Orca/OpenOrca), a popular instruction
dataset used for tuning LLM models. While the Lilac tool can scale to millions of rows on a single
machine, we are sampling to 100,000 so we can get started quickly.

```python
import lilac as ll

source = ll.HuggingFaceDataset(dataset_name='Open-Orca/OpenOrca', sample_size=100_000)
config = ll.DatasetConfig(namespace='local', name='open-orca-100k', source=source)
dataset = ll.create_dataset(config)
```

Output:

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
import lilac as ll
dataset = ll.get_dataset('local', 'open-orca-100k')
dataset.compute_signal(ll.PIISignal(), 'question')
dataset.compute_signal(ll.PIISignal(), 'response')
```

Output:

```sh
Computing pii on local/open-orca-100k:question: 100%|█████████████████████████████████████| 100000/100000 [03:36<00:00, 462.62it/s]
Computing signal "pii" on local/open-orca-100k:question took 216.246s.
Wrote signal output to ./data/datasets/local/open-orca-100k/question/pii
Computing pii on local/open-orca-100k:response: 100%|█████████████████████████████████████| 100000/100000 [02:21<00:00, 708.04it/s]
Computing signal "pii" on local/open-orca-100k:response took 141.312s.
Wrote signal output to ./data/datasets/local/open-orca-100k/response/pii
```

The dataset now has the extra fields `question.pii` and `response.pii`, which we can see by printing
the entire schema:

```py
print(dataset.manifest().data_schema)
```

Output:

```sh
id: string
system_prompt: string
question:
  pii:
    emails: list( string_span)
    ip_addresses: list( string_span)
    secrets: list( string_span)
response:
  pii:
    emails: list( string_span)
    ip_addresses: list( string_span)
    secrets: list( string_span)
  gte-small: list(
    embedding: embedding)
__hfsplit__: string
__rowid__: string
```

Note that `question.pii.emails` is a list of `string_span` values. These are objects with `start`
and `end` indices that point to the location of the email in the original `question` text.

Let's query 5 rows that have emails in the `response` field via [](#Dataset.select_rows), a python
API that is analogous to a `SQL Select` statement. We do this by adding an [`exists`](#Filter.op)
filter on `response.pii.emails` to make sure it's not empty:

```py
df_with_emails = dataset.select_rows(
  ['id', 'response', 'response.pii.emails'],
  limit=5,
  filters=[('response.pii.emails', 'exists')]).df()
print(df_with_emails)
```

Output:

```
             id                                           response                                response.pii.emails
0  flan.2166478  Subject: Bruce Colbourne, to D.Colbourne@ nrc-...  [{'__value__': {'start': 157, 'end': 183}}, {'...
1  flan.2168520  Once you have logged into your email account a...        [{'__value__': {'start': 482, 'end': 501}}]
2   flan.294964  Université McGill, 3550 Rue University, Montré...        [{'__value__': {'start': 174, 'end': 196}}]
3  flan.1805392  Step 1: Identify the words in the text.\n\nTo ...  [{'__value__': {'start': 274, 'end': 291}}, {'...
4    niv.204253  In this task, you are asked to translate an En...  [{'__value__': {'start': 322, 'end': 341}}, {'...
```

For more information on querying, see [](#Dataset.select_rows).

### Profanity detection

Let's also run the profanity concept on the `response` field to see if the LLM produced any profane
content. To do that we need to _index_ the `response` field using a text embedding. We only need to
index once. For a fast on-device embedding, we recommend the
[GTE-Small embedding](https://huggingface.co/thenlper/gte-small).

Before we can index with GTE-small, we need to install optional dependencies for the gte embedding:

```sh
pip install lilacai[gte]
```

```py
dataset.compute_embedding('gte-small', 'response')
```

Output:

```sh
Computing gte-small on local/open-orca-100k:('response',): 100%|█████████████████████████████████████| 100000/100000 [17:59<00:00, 92.67it/s]
Computing signal "gte-small" on local/open-orca-100k:('response',) took 1079.260s.
```

Now we can preview the top 5 responses based on their profanity concept score:

```py
search = ll.ConceptSearch(path='response', concept_namespace='lilac', concept_name='profanity', embedding='gte-small')
r = dataset.select_rows(['response'], searches=[search], limit=5)
print(r.df())
```

Output (the response text is removed due to sensitive content):

```
                                            response  ...                lilac/profanity/gte-small(response)
0                                  *****************  ...  [{'__value__': {'start': 0, 'end': 17}, 'score...
1                                  *****************  ...  [{'__value__': {'start': 0, 'end': 6}, 'score'...
2                                  *****************  ...  [{'__value__': {'start': 0, 'end': 143}, 'scor...
3                                  *****************  ...  [{'__value__': {'start': 0, 'end': 79}, 'score...
4                                  *****************  ...  [{'__value__': {'start': 0, 'end': 376}, 'scor...
```

To compute the concept score over the entire dataset, we do:

```py
dataset.compute_concept('lilac', 'profanity', embedding='gte-small', path='response')
```

Output:

```sh
Computing lilac/profanity/gte-small on local/open-orca-100k:('response',): 100%|█████████████████████████████████▉| 100000/100000 [00:10<00:00, 9658.80it/s]
Wrote signal output to ./data/datasets/local/open-orca-100k/response/lilac/profanity/gte-small/v34
```

## Download

Now that we’ve enriched the dataset, let’s download it so we can continue our work in a Python
notebook, or any other language. [](#Dataset.to_pandas) will create a DataFrame in memory. For other
formats see the other `.to_*()`[](#Dataset) methods. If you want to download only a subset of the
dataset, you can use the `columns` argument.

```py
df = dataset.to_pandas()
df.info()
```

Output:

```
 #   Column                                   Non-Null Count   Dtype
---  ------                                   --------------   -----
 0   id                                       100000 non-null  object
 1   system_prompt                            100000 non-null  object
 2   question                                 100000 non-null  object
 3   response                                 100000 non-null  object
 4   __hfsplit__                              100000 non-null  object
 5   response.pii                             100000 non-null  object
 6   response.lilac/profanity/gte-small/v34   100000 non-null  object
 7   question.pii                             100000 non-null  object
```
