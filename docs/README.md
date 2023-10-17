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

Logout if you are already logged in:

```bash
firebase logout
```

[Create a service account key](https://console.cloud.google.com/iam-admin/serviceaccounts/details/107201639375342680258/keys?project=lilac-386213)
for firebase and save it to your home directory at `~/.config/gcloud/lilac-firebase-key.json`.

Then set the environment variable (or add it to your `.bashrc` or `.zshrc`):

```bash
export GOOGLE_APPLICATION_CREDENTIALS='~/.config/gcloud/lilac-firebase-key.json'
```

### Deploy

```bash
poetry run python -m scripts.deploy_website
```

Append the `--staging` flag to deploy to the staging site instead of production.
