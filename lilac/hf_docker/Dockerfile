FROM python:3.11-slim-bullseye

# Allow statements and log messages to immediately appear in the Knative logs
ENV PYTHONUNBUFFERED True

# Adds GCC and other build tools so we can compile hnswlib and other native/C++ deps.
RUN apt-get update --fix-missing && apt-get install -y --fix-missing build-essential && \
  rm -rf /var/lib/apt/lists/*

# See: https://huggingface.co/docs/hub/spaces-sdks-docker#permissions
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
  PATH=/home/user/.local/bin:$PATH

# Set the working directory in the container.
WORKDIR $HOME/app

# Install the dependencies. This will look in ./dist for any wheels that match lilac. If they are
# not found, it will use the public pip package.

# Pip install lilac[all] and dependencies before trying to install the local image. This allows us
# to get cache hits on dependency installations when using a local wheel. When using the public pip
# package, the second call will be a no-op.
RUN python -m pip install lilac[all]

# Install from the local wheel inside ./dist. This will be a no-op if the wheel is not found.
COPY --chown=user /dist ./dist/
RUN python -m pip install --find-links=dist --upgrade lilac[all]

# Install the huggingface hub, used to download files.
RUN pip install huggingface_hub

# Copy the README so we can read the datasets from the HuggingFace config.
COPY --chown=user README.md .
# Copy the license just in case.
COPY --chown=user LICENSE .

COPY --chown=user docker_start.sh ./

# Make a local data directory for non-persistent storage demos.
RUN mkdir -p ./data
RUN chown -R user ./data

EXPOSE 5432
CMD ["bash", "docker_start.sh"]
