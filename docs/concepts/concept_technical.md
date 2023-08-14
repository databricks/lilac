# Concept technical details

**Concepts** are simply a collection of positive and negative examples.

**Concept models** instantiate a concept with an _embedding_.

Currently, the only supported concept model are
[sklearn logistic regression models](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html)
trained on top of embeddings. This means that training time can be on the order of milliseconds,
when embeddings are already computed. However, other implementations could be used in the future
(e.g. a fine-tuned model, or calling a generative model with a prompt).

Since concept models are linear models on top of embeddings, the quality if the embedding is crucial
to the quality of the concept model. If the embedding does not separate positive and negative
examples, nor will the final concept model. See [Embeddings](../embeddings/embeddings.md) for
details on chosing an embedding.

These models are the same size as a single vector of the training set. For example, an embedding
with 384 dimensions (32-bit floats) will be 1536 bytes (~1K). These models are pickled and saved to
disk in `DATA_PATH/.cache/lilac/concept/$NAMESPACE/$NAME`.
