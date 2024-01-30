# Python API

Lilac's UI is built atop a Python library, which you can access through the `lilac` module. The UI
generally defers all computation to Python, so if the feature is in the UI, you'll be able to do the
same from Python.

The UI excels at interactive exploration and tagging/deletion, while the Python API provides
powerful primitives, like `map`, which allows you to run arbitrary Python computations with
developer-friendly features like progress tracking and resumability.

To get the best of both worlds, you can run `ll.start_server()` in your Python notebook or
interpreter to start the Lilac backend as a background thread, and then continue with using the
Lilac API. (Running the Lilac server in the same Python process/kernel is recommended because Lilac
can then share the same database connections and in-memory caches, lowering memory usage and
ensuring data consistency between UI and API.)

In this quickstart, we're going to:

- Load [OpenOrca](https://huggingface.co/datasets/Open-Orca/OpenOrca), a popular instruction dataset
  for tuning LLMs.
- Compute clusters.
- Delete specific clusters.
- Find profanity in the remaining rows (using powerful text embeddings)
- Download the enriched dataset as a json file so we can clean it in a Python notebook

## Import lilac

```bash
pip install lilac[all]
```

```python
import lilac as ll

# Set the global project directory to where project files will be stored.
ll.set_project_dir('~/my_project')
```

## Create or load a dataset

Let's load [OpenOrca](https://huggingface.co/datasets/Open-Orca/OpenOrca), a popular instruction
dataset used for tuning LLM models. While the Lilac tool can scale to millions of rows on a single
machine, we are sampling to 10,000 so we can get started quickly.

```python
source = ll.HuggingFaceSource(dataset_name='Open-Orca/OpenOrca', sample_size=10_000)
config = ll.DatasetConfig(namespace='local', name='open-orca-10k', source=source)
dataset = ll.create_dataset(config)
```

Output:

```sh
Downloading data files: 100%|██████████████████████████████████████| 1/1 [05:14<00:00, 314.85s/it]
Extracting data files: 100%|███████████████████████████████████████| 1/1 [00:00<00:00, 318.98it/s]
Setting num_proc from 8 to 2 for the train split as it only contains 2 shards.
Generating train split: 4233923 examples [00:06, 654274.93 examples/s]
Dataset "open-orca-100k" written to ./data/datasets/local/open-orca-100k
```

Alternately, you can load a preexisting dataset:

```python
dataset = ll.get_dataset('local', 'open-orca-100k')
```

## Compute clusters

Let's compute clusters on the `question`field.

```python
dataset.cluster('question')
```

Output:

```sh
[local/open-orca-10k][1 shards] map "extract_text" to "('question__cluster',)": 100%|██████████| 10000/10000 [00:00<00:00, 59156.94it/s]
Wrote map output to question__cluster-00000-of-00001.parquet
[local/open-orca-10k][1 shards] map "cluster_documents" to "('question__cluster',)":   0%|          | 0/10000 [00:00<?, ?it/s]
jinaai/jina-embeddings-v2-small-en using device: mps:0
Computing embeddings: 100%|██████████| 10000/10000 [18:30<00:00,  9.01it/s]
Computing embeddings took 1113.504s.
UMAP: Reducing dim from 512 to 5 of 10000 vectors took 21.791s.
HDBSCAN: Clustering took 0.175s.
4515 noise points (45.1%) will be assigned to nearest cluster.
[local/open-orca-10k][1 shards] map "cluster_documents" to "('question__cluster',)": 100%|██████████| 10000/10000 [19:13<00:00,  8.67it/s]
HDBSCAN: Computing membership for the noise points took 15.788s.
Wrote map output to question__cluster-00000-of-00001.parquet
[local/open-orca-10k][1 shards] map "title_clusters" to "('question__cluster',)": 100%|██████████| 10000/10000 [00:26<00:00, 374.38it/s]
Wrote map output to question__cluster-00000-of-00001.parquet
Computing embeddings: 10000it [01:19, 125.71it/s]es
Computing embeddings took 79.760s.
UMAP: Reducing dim from 512 to 5 of 10000 vectors took 53.578s.
HDBSCAN: Clustering took 0.136s.
137 noise points (1.4%) will be assigned to nearest cluster.
[local/open-orca-10k][1 shards] map "cluster_titles" to "('question__cluster',)": 100%|██████████| 10000/10000 [02:14<00:00, 74.37it/s]
HDBSCAN: Computing membership for the noise points took 0.426s.
Wrote map output to question__cluster-00000-of-00001.parquet
[local/open-orca-10k][1 shards] map "title_categories" to "('question__cluster',)": 100%|██████████| 10000/10000 [00:25<00:00, 395.07it/s]
Wrote map output to question__cluster-00000-of-00001.parquet
[local/open-orca-10k][1 shards] map "drop_temp_text_column" to "('question__cluster',)": 100%|██████████| 10000/10000 [00:00<00:00, 71313.87it/s]
Wrote map output to question__cluster-00000-of-00001.parquet
```

The dataset now has the extra fields `question__cluster`, which we can see by printing the entire
schema:

```py
print(dataset.manifest().data_schema)
```

Output:

```sh
id: string
system_prompt: string
question: string
response: string
__hfsplit__: string
question__cluster:
  cluster_id: int32
  cluster_membership_prob: float32
  cluster_title: string
  category_id: int32
  category_membership_prob: float32
  category_title: string
```

## Select specific rows

Let's find all clusters that talk about movies via [](#Dataset.select_rows), which works very
similarly to a `SQL Select` statement. We do this by adding an [`exists`](#Filter.op) filter on
`question__cluster.cluster_title`.

```py
df_with_emails = dataset.select_rows(
  ['id', 'question', 'question__cluster.cluster_title', 'question__cluster.cluster_id'],
  limit=5,
  filters=[('question__cluster.cluster_title', 'regex_matches', '[Mm]ovie')]).df()
print(df_with_emails)
```

Output:

```
             id                                           question  \
0    t0.1073241  Answer the following question: Write a multi-c...
1  flan.1059135  Choose the correct sentiment from candidates:\...
2  flan.1794922  The "math" aspect to this is merely a gimmick ...
3     t0.243847  Q:Read the following paragraph and extract the...
4     t0.265856  Please answer the following question: Generate...

               question__cluster.cluster_title  question__cluster.cluster_id
0            Answering Movie-Related Questions                           320
1                      Movie Review Sentiments                           286
2  Extracting Answers from Vampire Movie Plots                           325
3          Extracting Answers from Movie Plots                           313
4                         Movie Plot Questions                           371
```

After confirming the results of this query, let's delete these rows:

```py
dataset.delete_rows(filters=[('question__cluster.cluster_title', 'regex_matches', '[Mm]ovie')])
print(dataset.count(), 'rows remaining')
```

Output:

```
9174 rows remaining
```

For more information on querying, see [](#Dataset.select_rows).

### Profanity detection

Let's also run the profanity concept on the `response` field to see if the LLM produced any profane
content. To do that we need to _index_ the `response` field using a text embedding. We only need to
index once. For a fast on-device embedding, we recommend the
[GTE-Small embedding](https://huggingface.co/thenlper/gte-small).

```py
dataset.compute_embedding('gte-small', 'response')
```

Output:

```sh
Compute embedding  GTESmall({"embed_input_type":"document","signal_name":"gte-small"}) on open-orca-10k:response: 100%|██████████| 9174/9174 [04:47<00:00, 31.93it/s]

```

Now we can preview the top 5 responses based on their profanity concept score:

```py
search = ll.ConceptSearch(path='response', concept_namespace='lilac', concept_name='profanity', embedding='gte-small')
r = dataset.select_rows(['response'], searches=[search], limit=5)
print(r.df())
```

Output:

```
Computing topk on local/open-orca-10k:('response',) with embedding "gte-small" and vector store "hnsw" took 0.062s.
Computing signal "concept_labels" on local/open-orca-10k:('response',) took 0.012s.
Computing signal "concept_score" on local/open-orca-10k:('response',) took 0.025s.
                                            response  \
0  Part #1: Understand the text from a social med...
1  - Years active: Early 2000s to present\n- Birt...
2                                                sex
3  Sure! In a simple way for you to understand, t...
4  The nursery rhyme "Ding, Dong, Bell," also kno...

          response.lilac/profanity/gte-small/preview
0  [{'__span__': {'start': 0, 'end': 113}, 'score...
1  [{'__span__': {'start': 0, 'end': 103}, 'score...
2  [{'__span__': {'start': 0, 'end': 3}, 'score':...
3  [{'__span__': {'start': 0, 'end': 78}, 'score'...
4  [{'__span__': {'start': 0, 'end': 164}, 'score...
```

To compute the concept score over the entire dataset, we do:

```py
dataset.compute_concept('lilac', 'profanity', embedding='gte-small', path='response')
```

Output:

```sh
Compute signal  ConceptSignal({"embedding":"gte-small","namespace":"lilac","concept_name":"profanity","version":36,"draft":"main","signal_name":"concept_score"}) on open-orca-10k:response: 100%|██████████| 9174/9174 [00:01<00:00, 7322.02it/s]
Wrote signal output to data/datasets/local/open-orca-10k/response/lilac/profanity/gte-small
```

## Convert formats

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
<class 'pandas.core.frame.DataFrame'>
RangeIndex: 9174 entries, 0 to 9173
Data columns (total 7 columns):
 #   Column             Non-Null Count  Dtype
---  ------             --------------  -----
 0   id                 9174 non-null   object
 1   system_prompt      9174 non-null   object
 2   question           9174 non-null   object
 3   response           9174 non-null   object
 4   __hfsplit__        9174 non-null   object
 5   question__cluster  9174 non-null   object
 6   __deleted__        0 non-null      object
dtypes: object(7)
memory usage: 501.8+ KB
```
