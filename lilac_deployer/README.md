# HuggingFace deploy a dataset to a space UI.

This folder contains the standalone webserver that lets a user deploy a Lilac instance for a
HuggingFace dataset to a HuggingFace space.

[Demo](https://huggingface.co/spaces/lilacai/lilac_deployer)

### Development

To run the server locally (make sure the CWD is this directory):

```sh
poetry run streamlit run app.py
```

In VSCode, make sure to switch the default intepreter to the one in this folder.

### Deployment

To deploy the server, run:

```sh
poetry run python -m scripts.deploy_lilac_deployer
```
