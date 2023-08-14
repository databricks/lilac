# Embeddings

Embeddings are used in Lilac for Concepts, for Semantic Similarity, and for embedding-based signals.

The choice of an embedding can be crucial for a well-performing downstream signal.

Lilac has built-in **on device** embeddings:

- [`gte-small`](https://huggingface.co/thenlper/gte-small): Gegeral Text Embeddings (GTE) model
  (small).
- [`gte-base`](https://huggingface.co/thenlper/gte-base): Gegeral Text Embeddings (GTE) model
  (base).
- [`sbert`](https://www.sbert.net/docs/pretrained_models.html#sentence-embedding-models/):
  SentenceTransformers text embeddings.

Lilac has built-in **remote** embeddings. Using these will _send data to an external server_:

- [`openai`](https://platform.openai.com/docs/api-reference/embeddings): OpenAI embeddings. You will
  need to define `OPENAI_API_KEY` in your environment variables.
- [`cohere`](https://docs.cohere.com/docs/embeddings): Cohere embeddings. You will need to define
  `COHERE_API_KEY` in your environment variables.
- [`palm`](https://cloud.google.com/vertex-ai/docs/generative-ai/embeddings/get-text-embeddings)
  PaLM embeddings. You will need to define `PALM_API_KEY` in your environment variables.

## Register your own embedding

You can register your own embedding in Python:

```python

class MyEmbedding(ll.TextEmbeddingSignal):
  name: 'my_embedding'
  def setup(self):
    # Do your one-time setup here.
    pass

  def compute(self, docs):
    def embed_fn(texts: list[str]):
      # Compute your embedding matrix for the batch of text here. This return a matrix with
      # dimensions [batch_size, embedding_dims].
      return your_embedding(texts)

    for doc in docs:
      # Split the text, and compute embeddings for each split,
      yield from ll.compute_split_embeddings(
        docs=docs,
        batch_size=64,
        embed_fn,
        # Use the lilac chunk splitter.
        split_fn=ll.split_text,
        # How many batches to request as a single unit.
        num_parallel_requests=1)

ll.register_signal(MyEmbedding)
```

After you create a custom embedding and register it, you will be able to use it as `my_embedding`.
