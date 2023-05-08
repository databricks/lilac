# type: ignore
"""Currently fake integration tests for end to end functionality.

NOTE: This code does not run! It is just what we're building towards. That's why everything is
ignored.
"""
# pylint: disable-all
# mypy: ignore-errors
# flake8: noqa


def db_integration_test_fake():
  location = DatasetLocation(path='/local/path')
  db = DatasetDuckDB(namespace='local', name='my_dataset', location=location)

  # Yells because there is no dataset in this location.
  db.select_rows()

  # Load data from a dataframe, or a source config to find data.
  db.load_from(df)
  db.load_from(SourceConfig())

  # Works because we've loaded a dataset.
  db.select_rows()

  # Loading the db again, from the same directory, gives a cache-hit beacuse we've loaded something
  # to that location already with that dataset name.
  db = DatasetDuckDB(namespace='local', name='my_dataset', location=location)

  # Works because we've loaded a dataset, and it's a cache hit.
  db.select_rows()

  ## Simple signals.
  # Both of these yell, there is not yet a Signal column computed for text.
  db.select_rows(columns=[Signal(Column('text'), signal='word_count')])
  db.select_rows(columns=[Signal(Column('text'), signal=WordCount)])

  # Only use one of these, the first uses a registry, the second is your own function. This writes
  # the signal output to a file next to the dataset.
  db.compute_signal_column(Column('text'), signal='word_count')
  db.compute_signal_column(Column('text'), signal=WordCount)

  # Either of these work now because we've written another parquet file to disk for the signal over
  # the text column.
  db.select_rows(columns=[Signal(Column('text'), signal='word_count')])
  db.select_rows(columns=[Signal(Column('text'), signal=WordCount)])

  ## Concept signals.

  # Yells because the concept needs to be precomputed on the column.
  db.select_rows(columns=[Signal(Column('text'), signal='toxicity_cohere_embeddings')])

  # Precompute the concept on the column.
  db.compute_signal_column(Column('text'), signal='toxicity_cohere_embeddings')
  toxicity_cohere_embeddings = ConceptModel()
  db.compute_signal_column(Column('text'), signal=toxicity_cohere_embeddings)
  # Now the concept parquet file has been written to disk, with a version in the filename.

  # Now works because we've written the concept parquet file to disk.
  db.select_rows(columns=[Signal(Column('text'), signal='toxicity_cohere_embeddings')])

  ## Nearest neighbors & semantic similarity.

  # Yells because the embedding index has not been computed (or it doesnt yell if the embedding
  # happens to be shared from a model before for that column)
  db.select_rows(
    columns=[SemanticSimilarity(Column('text'), text='hello world', embedding='cohere')])

  # This line may share embeddings the toxicity model from before.
  db.compute_semantic_index(Column('text'), embedding='cohere')

  # This now works because we've computed the index.
  db.select_rows(
    columns=[SemanticSimilarity(Column('text'), text='hello world', embedding='cohere')])
