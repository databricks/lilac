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

To deploy the website:

One time setup: `npm install -g firebase-tools`

```bash
./scripts/deploy_website.sh
```
