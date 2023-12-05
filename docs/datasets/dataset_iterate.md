# Iterating on a dataset

```{note}
This page goes into the technical details of iterating on a dataset in Lilac.
For a real world example, see the blog post on [](../blog/better-curate.md).
```

## `Dataset.map`

[`Dataset.map`](#Dataset.map) is the main vehicle of doing processing and updating the dataset. It's
similar to [HuggingFace's Dataset.map()](https://huggingface.co/docs/datasets/process#map) with a
few key differences:

- The output of Lilac's `Dataset.map` is a new column attached to the existing dataset. This enables
  tracking of lineage information for every computed column, while avoiding copying the entire
  dataset over.
- If the map fails mid-way (e.g. with an exception, or your computer dies), you can resume
  computation without losing any intermediate results. This is important when the `map` function is
  expensive or slow (e.g. calling GPT to edit data, or calling an expensive embedding model).
- The map must return a single item or `None`, for each input item. This allows us to track how each
  item is transformed.
- When the computation is done, the Lilac UI will auto-refresh and we'll see the new column
  immediately.

In the following example, we will add a prefix to each "question" field in the dataset.

```python
def add_prefix(item):
  return 'Q: ' + item['question']

dataset.map(add_prefix, output_column='question_prefixed')
```

### `input_path`

For faster disk reads and simpler `map` function, we can provide `input_path='question'`, which will
tell Lilac to only read the `question` field from disk and pass it to the `map` function.

```python
def add_prefix(question):
  return 'Q: ' + question

dataset.map(add_prefix, input_path='question', output_column='question_prefixed')
```

`input_path` can be very useful when transforming an arbitrarily nested list, because Lilac can
handle nested inputs and mimic the same nested structure in the output column.

Let's make a new dataset with a nested list of questions:

```python

items = [
  {'questions': ['A', 'B']},
  {'questions': ['C']},
  {'questions': ['D', 'E']},
]
config = ll.DatasetConfig(
  namespace='local',
  name='tutorial2',
  source=ll.DictSource(items),
)
dataset = ll.create_dataset(config)
dataset.to_pandas()
```

```
       questions.*
0      [A, B]
1         [C]
2      [D, E]
```

Let's do the map again, but this time we'll use `input_path=('questions', '*')` to tell Lilac to map
over each individual item in the `questions` list. This is equivalent to mapping over the flattened
list `['A', 'B', 'C', 'D', 'E']`.

```python
def add_prefix(question):
  return 'Q: ' + question

dataset.map(add_prefix, input_path=('questions', '*'), output_column='questions_prefixed')
dataset.to_pandas()
```

```
Scheduling task "51092ecf44a547c39b14d2d8e56a6faf": "[local/tutorial2][1 shards] map "add_prefix" to "questions_prefixed"".
Wrote map output to ./datasets/local/tutorial2/questions_prefixed-00000-of-00001.parquet
[Shard 0/1] map "add_prefix" to "('questions_prefixed',)": 100%|██████████| 3/3 [00:00<00:00, 1100.19it/s]

       questions.*       questions_prefixed.*
0      [A, B]            [Q: A, Q: B]
1         [C]                  [Q: C]
2      [D, E]            [Q: D, Q: E]
```

We can see that the `questions_prefixed` column is a nested list, with the same structure as the
`questions` column.

### Structured output
