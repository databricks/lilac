# Shedding light on AI datasets

August 21, 2023 <br/> _Daniel Smilkov & Nikhil Thorat_

During our time at Google, we had the opportunity to collaborate with over 20 teams and improve
numerous datasets used for training AI models. The main objective of these teams was to ensure the
quality of their models, often focusing on refining the training data itself.

What makes refining data difficult is that AI models rely on unstructured data, such as natural
language or images, that lack any labels or useful metadata. To complicate matters, what constitutes
“good” data depends heavily on the application and the user experience. Despite these differences, a
common thread emerged: while each team would compute big-picture statistics and understood the
general composition of their data, they often overlooked the raw data. Moreover, cleaning data was
done with heuristics with an accompanying python script with little visibility into the side effects
of that change. When we asked teams to describe “bad” data, they often couldn’t define it, but they
all knew bad data when they saw it. In other cases, “bad” data isn’t objectively bad: for instance,
the presence of German in a French => English translation dataset. With that observation in mind, we
built tools and processes that empowered teams to see their data. To summarize a few years of
learning into one sentence: each dataset has its own quirks, and these quirks can have non-obvious
implications for the quality of downstream models.

At Lilac, our mission is to make unstructured data **visible**, **quantifiable**, and **malleable**.

As a first step, we are open-sourcing a tool that enables AI practitioners to see and quantify their
datasets. Since each team and application has its own requirements, we’re focused on enabling users
to annotate data along customizable concepts. These AI-powered concepts can be specific to an
application, e.g. termination clauses in legal contracts, or generally applicable, e.g. toxicity.

<video loop muted autoplay controls src="https://github-production-user-asset-6210df.s3.amazonaws.com/2294279/260771834-cb1378f8-92c1-4f2a-9524-ce5ddd8e0c53.mp4"></video>

At Lilac, we care about data privacy so we are focused on making the product fast and usable with
data staying on-premise. We use powerful on-device embeddings, like GTE, to power Concepts. However
if your application is not sensitive to data privacy (e.g. using open-source datasets), you may
choose to use more powerful embeddings like OpenAI, Cohere, PaLM, or your own!

We are also hosting [a HuggingFace space](https://huggingface.co/spaces/lilacai/lilac) with a
handful of popular datasets (e.g. [OpenOrca](https://huggingface.co/datasets/Open-Orca/OpenOrca))
and curated concepts (e.g. profanity, legal termination, source-code detection). In this demo, you
can browse pre-enriched datasets and create your own concepts. This HuggingFace space can also be
forked, and made private with your own data, skipping the installation process of Lilac.

We hope the community will try the tool and help us grow a central repository of useful concepts. We
would love to collaborate and shed light on the most popular AI datasets. Let’s visualize, quantify,
and ultimately improve all unstructured datasets.

Daniel & Nikhil
