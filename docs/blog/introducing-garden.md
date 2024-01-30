# 100x Faster Clustering with Lilac Garden

_Jan 30, 2024_

_Automatic and human-readable clustering of 1 million conversations from Chatbot Arena, computed in
20 minutes.
[Join the waitlist for Lilac Garden.](https://docs.google.com/forms/d/e/1FAIpQLSd53PiLVU-65n0czUbhQySvZVtybbSR1fH-WJDDycOZxVRvNQ/viewform)_

<a href="https://lilacai-lilac.hf.space/datasets#lilac/lmsys-chat-1m&query=%7B%7D&viewPivot=true&pivot=%7B%22outerPath%22%3A%5B%22conversation__clusters%22%2C%22category_title%22%5D%2C%22innerPath%22%3A%5B%22conversation__clusters%22%2C%22cluster_title%22%5D%7D">
<img title="Cluster view of conversations from Chatbot Arena" src="../_static/introducing_garden/clusters.png" />
</a>

At Lilac, our mission is to help you understand and curate your text data so you can build the best
possible LLM apps. We’ve built a new LLM-powered text clustering pipeline that’s more accurate and
easy to understand than any clustering approach we’ve seen before. This is our first cloud service
that we are launching on [Lilac Garden](https://www.lilacml.com/#garden), our new accelerated
computation platform.

## The problem

Understanding text datasets poses a unique set of challenges. Unlike images and videos where we
immediately can _see_ patterns, text requires a different approach. A common approach to
understanding large text datasets is clustering, where semantically similar documents are put in the
same bucket, or category. Understanding the relative sizes of the categories allows us to understand
how our data is distributed, without having to read every individual document. However document
clustering is often tricky to get right, requiring embeddings that capture intent in text, and
compute intensive pipelines that can take prohibitively long. The result is a set of cluster IDs
that require skimming through individual examples to draw insights.

## Our solution

Our new clustering service aims to solve this problem by simplifying this pipeline to a single API
that allows you to hand us a list of documents, and we'll give you back human-readable cluster
names, and categories for clusters, with a highly-optimized, hardware-accelerated cloud pipeline.

We leverage long context embeddings, massively parallel GPU compute, and sophisticated LLMs to
generate concise, descriptive titles for each cluster. These clusters play a crucial role in
revealing the major segments of your dataset by grouping similar documents together. This approach
can dramatically speed up the process of curation, allowing the identification and removal of
problematic clusters, sub-sampling large clusters to reduce dataset size, and creating task-specific
datasets. Moreover, examining clusters in user-LLM interaction logs sheds light on subtle and
potentially hazardous ways in which users engage with your product.

Don’t just take our word for it - check out Lilac’s demo page to see clusters for LLM fine-tuning
datasets
([OpenOrca](https://lilacai-lilac.hf.space/datasets#lilac/OpenOrca&viewPivot=true&pivot=%7B%22outerPath%22%3A%5B%22question__cluster%22%2C%22category_title%22%5D%2C%22innerPath%22%3A%5B%22question__cluster%22%2C%22cluster_title%22%5D%7D),
[Capybara](https://lilacai-lilac.hf.space/datasets#lilac/Capybara&viewPivot=true&pivot=%7B%22outerPath%22%3A%5B%22conversation_input__cluster%22%2C%22category_title%22%5D%2C%22innerPath%22%3A%5B%22conversation_input__cluster%22%2C%22cluster_title%22%5D%7D),
[UltraChat](https://lilacai-lilac.hf.space/datasets#lilac/UltraChat-200k&query=%7B%7D&viewPivot=true&pivot=%7B%22outerPath%22%3A%5B%22messages__clusters%22%2C%22category_title%22%5D%2C%22innerPath%22%3A%5B%22messages__clusters%22%2C%22cluster_title%22%5D%7D),
[Glaive](https://lilacai-lilac.hf.space/datasets#lilac/glaive-code-assistant&viewPivot=true&pivot=%7B%22outerPath%22%3A%5B%22question__cluster%22%2C%22category_title%22%5D%2C%22innerPath%22%3A%5B%22question__cluster%22%2C%22cluster_title%22%5D%7D),
[SlimOrca](https://lilacai-lilac.hf.space/datasets#lilac/SlimOrca&query=%7B%7D&viewPivot=true&pivot=%7B%22outerPath%22%3A%5B%22conversation__clusters%22%2C%22category_title%22%5D%2C%22innerPath%22%3A%5B%22conversation__clusters%22%2C%22cluster_title%22%5D%7D)),
LLM eval datasets
([MMLU](https://lilacai-lilac.hf.space/datasets#lilac/MMLU&query=%7B%7D&viewPivot=true&pivot=%7B%22outerPath%22%3A%5B%22question__cluster%22%2C%22category_title%22%5D%2C%22innerPath%22%3A%5B%22question__cluster%22%2C%22cluster_title%22%5D%7D),
[ARC](https://lilacai-lilac.hf.space/datasets#lilac/ARC-Challenge&query=%7B%7D&viewPivot=true&pivot=%7B%22outerPath%22%3A%5B%22question__cluster%22%2C%22category_title%22%5D%2C%22innerPath%22%3A%5B%22question__cluster%22%2C%22cluster_title%22%5D%7D),
[Winogrande](https://lilacai-lilac.hf.space/datasets#lilac/WinoGrande&query=%7B%7D&viewPivot=true&pivot=%7B%22outerPath%22%3A%5B%22sentence__cluster%22%2C%22category_title%22%5D%2C%22innerPath%22%3A%5B%22sentence__cluster%22%2C%22cluster_title%22%5D%7D)),
user logs
([Chatbot Arena](https://lilacai-lilac.hf.space/datasets#lilac/lmsys-chat-1m&viewPivot=true&pivot=%7B%22outerPath%22%3A%5B%22conversation__clusters%22%2C%22category_title%22%5D%2C%22innerPath%22%3A%5B%22conversation__clusters%22%2C%22cluster_title%22%5D%7D)),
content scraping
([HN comments](https://lilacai-lilac.hf.space/datasets#lilac/hncomments-1m&query=%7B%7D&viewPivot=true&pivot=%7B%22outerPath%22%3A%5B%22text__cluster%22%2C%22category_title%22%5D%2C%22innerPath%22%3A%5B%22text__cluster%22%2C%22cluster_title%22%5D%7D)),
and more.

## Jailbreak clusters

[ChatBot Arena](https://chat.lmsys.org/) is a website that allows users to interact with and compare
chatbot quality. The Arena team has released a subset of redacted user logs, and we discovered that
quite a few users test their jailbreaks and prompt injections on the Arena.

<a href="https://lilacai-lilac.hf.space/datasets#lilac/lmsys-chat-1m&query=%7B%22filters%22%3A%5B%7B%22path%22%3A%5B%22conversation__clusters%22%2C%22category_title%22%5D%2C%22op%22%3A%22equals%22%2C%22value%22%3A%22Inappropriate%20Content%22%7D%5D%7D&groupBy=%7B%22path%22%3A%5B%22conversation__clusters%22%2C%22cluster_title%22%5D%2C%22value%22%3A%22Inappropriate%20Content%20Requests%22%7D">
  <img title="Jailbreaking models" src="../_static/introducing_garden/jailbreak_unhinged.png"/>
</a>

<a href="https://lilacai-lilac.hf.space/datasets#lilac/lmsys-chat-1m&query=%7B%22filters%22%3A%5B%7B%22path%22%3A%5B%22conversation__clusters%22%2C%22category_title%22%5D%2C%22op%22%3A%22equals%22%2C%22value%22%3A%22AI%20Role-Play%22%7D%5D%7D&groupBy=%7B%22path%22%3A%5B%22conversation__clusters%22%2C%22cluster_title%22%5D%2C%22value%22%3A%22Role-playing%20scenarios%20with%20DAN%20AI%20model%22%7D">
  <img title="DAN Jailbreak" src="../_static/introducing_garden/jailbreak_dan.png"/>
</a>

Unsurprisingly, another popular theme is users trying to get chatbots to say NSFW things (and they
seem to be broadly successful).

```{warning}
The image below links to explicit content.
```

<a href="https://lilacai-lilac.hf.space/datasets#lilac/lmsys-chat-1m&groupBy=%7B%22path%22%3A%5B%22conversation__clusters%22%2C%22category_title%22%5D%2C%22value%22%3A%22Inappropriate%20Content%22%7D&rowId=%22fff8851628884e259af503b0570ba194%22">
<img title="NSFW" src="../_static/introducing_garden/nsfw.png"/>

</a>

Users are also trying to understand the guardrails of the chatbots by poking around controversial
topics.

<a href="https://lilacai-lilac.hf.space/datasets#lilac/lmsys-chat-1m&groupBy=%7B%22path%22%3A%5B%22conversation__clusters%22%2C%22category_title%22%5D%2C%22value%22%3A%22AI%20Ethics%20Conversations%22%7D&rowId=%22ff6668747746466ca528b1912133926a%22">
  <img title="AI Ethics" src="../_static/introducing_garden/ai_ethics.png"/>
</a>

Our cluster breakdown page also supports grouping by custom fields. We can
<a href="https://lilacai-lilac.hf.space/datasets#lilac/lmsys-chat-1m&viewPivot=true&pivot=%7B%22outerPath%22%3A%5B%22model%22%5D%2C%22innerPath%22%3A%5B%22conversation__clusters%22%2C%22cluster_title%22%5D%7D">group
by the Model column</a> to see what sorts of interactions users have with each model.

<a href="https://lilacai-lilac.hf.space/datasets#lilac/lmsys-chat-1m&viewPivot=true&pivot=%7B%22outerPath%22%3A%5B%22model%22%5D%2C%22innerPath%22%3A%5B%22conversation__clusters%22%2C%22cluster_title%22%5D%7D">
  <img title="Grouping cluster by model type" src="../_static/introducing_garden/group_cluster_by_model.png" />
</a>

We’re excited to see what interesting clusters you find!

## Clustering, powered by Lilac Garden

Lilac users can pip install the latest version on PyPI to run
[clustering locally](https://docs.lilacml.com/datasets/dataset_cluster.html). Local clustering works
reasonably well up to ~10,000 data points, but it will take a few hours. For users with a GPU and
CuML installed, datasets of ~100,000 points should be feasible.

To cluster a dataset is simple, without any hyperparameters.

```py
import lilac as ll
dataset = ll.from_huggingface('LDJnr/Capybara')
dataset.cluster(input='conversation.*.input', use_garden=False)
```

For datasets larger than 10k rows – or if you’re impatient, like us –
[Lilac Garden](https://www.lilacml.com/#garden) is a remote computation service that powers
compute-heavy features like clustering, perplexity scoring, and embedding computation. Lilac Garden
clustered our largest datasets of 4 million data points in just an hour. A 10,000 data point dataset
would cluster in less than a minute on Garden - **100x faster** than local computation!

Lilac Garden fundamentally changed how we interact with data, allowing to use the power of LLMs over
entire datasets, without needing to wait and monitor multi-day pipelines.

To join the waitlist,
[fill out this form](https://docs.google.com/forms/d/e/1FAIpQLSd53PiLVU-65n0czUbhQySvZVtybbSR1fH-WJDDycOZxVRvNQ/viewform).

### How we did it

Historically, clustering as a service has been hard to pull off for several reasons:

- Clustering is slow! (A 10k row dataset takes 15 minutes on an M2 Pro Macbook)
- Clustering requires the entire dataset to be in RAM. Each new dataset requires fiddling with
  clustering hyperparameters
- The dependencies are fiddly
- Finding a good embedding function is hard
- Even after you get your clusters, it’s hard to understand what each of the thousands of clusters
  actually are.

Today, these issues are all solvable, thanks to the work of many other companies and researchers.

The Lilac Clustering pipeline is a four-step process.

1. Embed documents with
   [Jina V2](https://jina.ai/news/jina-ai-launches-worlds-first-open-source-8k-text-embedding-rivaling-openai/),
   which supports embedding long documents with a single embedding.
1. Reduce the dimensionality using [UMAP](https://umap-learn.readthedocs.io/en/latest/), which
   projects hundreds to thousands of embedding dimensions to a much smaller size, emphasizing
   scale-free local structure, and feeding well into HDBScan’s cluster detection algorithm.
1. Compute clusters with [HDBScan](https://hdbscan.readthedocs.io/en/latest/how_hdbscan_works.html),
   enabling clustering without extensive hyperparameter tuning.
1. Attach human-legible titles to these clusters by asking [GPT](https://openai.com/product) to
   title the cluster.

![Clustering pipeline](../_static/introducing_garden/cluster_pipeline.png)

This process, run once, generates fine-grained clusters like _"Translating English to Czech"_ and
_"Persian-English Translation"_. We then repeat the process on the generated titles to create
cluster categories, like _"Translation"_, which categorizes the fine-grained clusters from the first
phase of the pipeline.

Thanks to the wizards at NVidia, [CuML](https://docs.rapids.ai/api/cuml/stable/) can accelerate
these computations tenfold. Then, we rely on [Modal](https://modal.com) to provide parallel GPUs and
a RPC framework to schedule all of these computations. The final step is to put a human-legible
label on these clusters by prompt-engineering a command to GPT3.5.

### Beyond clusters

Clustering can give us valuable insights into the shape of our data, or how users are interacting
with production systems. However, we can also use the generated clusters to curate data much faster
in Lilac:

- Drop problematic clusters
- Sample across clusters to reduce the size of our dataset
- Create a task-specific dataset from a much larger dataset

We’ve uploaded all of the clustered datasets (with cluster titles and cluster IDs) at our
[HuggingFace page](https://huggingface.co/lilacai).

[Here’s a notebook](https://github.com/lilacai/lilac/blob/main/notebooks/ClusterSampling.ipynb) that
demonstrates how to download and filter using our clusters, using Translation clusters in SlimOrca
to create a translation-only SlimOrca dataset.

We’re excited to see what you end up doing with the clusters!
