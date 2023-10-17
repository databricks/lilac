## Lilac documentation

We use Sphinx to auto-generate the API reference.

**_NOTE:_** Run all scripts from the project root.

For development, start a local server with auto-refresh:

```bash
./scripts/watch_docs.sh
```

To build the docs:

```bash
./scripts/build_docs.sh
```

## Deployment

### One time setup (skip to [Deploy](#Deploy))

Install firebase cli:

```bash
npm install -g firebase-tools
```

### Deploy

```bash
poetry run python -m scripts.deploy_website
```

Append the `--staging` flag to deploy to the staging site instead of production.
