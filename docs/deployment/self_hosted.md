# Self-hosting Lilac

By self-hosting, you can keep your data on-prem.

## Run via command line

By default, Lilac runs on port `5432`.

```sh
pip install lilac[all]
lilac start /data
```

## Run via Docker

Build the image after cloning the repo:

```sh
git clone https://github.com/lilacai/lilac.git
docker build -t lilac .
```

The container runs on the virtual port `8000`, this command maps it to the host machine port `5432`.

If you have an existing lilac project, mount it and set the `LILAC_PROJECT_DIR` environment
variable:

```sh
docker run -it \
  -p 5432:8000 \
  --volume /host/path/to/data:/data \
  -e LILAC_PROJECT_DIR="/data" \
  lilac
```
