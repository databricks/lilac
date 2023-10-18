# Export data

```{tip}
[Download enrichments for popular datasets on HuggingFace](https://lilacai-lilac.hf.space/)
```

Once we've computed signals and concepts over a dataset, it can be very useful to download the
results so downstream applications can used the enrichments.

## From the UI

We can download the results by clicking the Download icon in the top-right of the dataset view:

<img width=360 src="../_static/dataset/dataset_download_icon.png"></img>

This will open a modal which lets you choose fields to download, with a preview of the download
results:

<img src="../_static/dataset/dataset_download_modal.png"></img>

Click "Download" to download the results as a JSON file from the browser.

## From Python

In Python, we can export to different formats using the [](#Dataset.to_pandas),
[](#Dataset.to_json), [](#Dataset.to_parquet) and [](#Dataset.to_csv) methods.

Let's export the `text` and `text.language_detection` to a pandas dataframe:

```python
dataset = ll.get_dataset('local', 'imdb')
# NOTE: you can also select lang detection with ('text', 'language_detection')
df = dataset.to_pandas(columns=['text', 'text.lang_detection'])
print(df)
```

Let's export all the columns to a JSONL file:

```python
dataset.to_json('imdb.jsonl', jsonl=True)
```

### Labels

If you have manually labeled some of the rows, you can choose to only export rows that **include** a
certain label:

```python
dataset.to_json('imdb.jsonl', jsonl=True, include_labels=['good_data'])
```

or rows that **exclude** a certain label:

```python
dataset.to_json('imdb.jsonl', jsonl=True, exclude_labels=['bad_data'])
```

### Filtering

We can also filter the rows we export. The filter API is the same as in
[Dataset.select_rows](./dataset_query.md#filters). For example, let's only export rows where the
language is `en`:

```python
dataset.to_json('imdb.jsonl', jsonl=True, filters=[('text.lang_detection', 'equals', 'en')])
```

or where the toxicity is < 0.3:

```python
dataset.to_json('imdb.jsonl', jsonl=True, filters=[('text.lilac/toxicity/gte-small.score', 'less', 0.3)])
```
