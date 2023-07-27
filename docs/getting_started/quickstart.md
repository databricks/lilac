# Quick Start

```{tip}
Make sure you've followed the [installation](installation.md) steps first.
```

Start the lilac web server.

```bash
lilac start
```

This should open a browser tab pointing to `http://localhost:5432`.

## Adding a dataset

Let's load a small dataset with movie descriptions.
Click the "Add dataset" button on the Getting Started page. Choose the `csv` loader and paste in
the following URL in the Filepaths section:

```
https://storage.googleapis.com/lilac-data-us-east1/datasets/csv_datasets/the_movies_dataset/the_movies_dataset.csv
```

Click the "Add" button on the bottom on start a background job to load the dataset.

<video loop muted autoplay controls src="../_static/getting_started/add-dataset.mp4"></video>
