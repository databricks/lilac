# NOTE: When we upgrade to 3.11 we can use a slimmer docker image which comes with gcc.
FROM python:3.9-bullseye

# Allow statements and log messages to immediately appear in the Knative logs
ENV PYTHONUNBUFFERED True

# See: https://huggingface.co/docs/hub/spaces-sdks-docker#permissions
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
	PATH=/home/user/.local/bin:$PATH

# Set the working directory in the container.
WORKDIR $HOME/app

# Install the dependencies. This will look in ./dist for any wheels that match lilac. If they are
# not found, it will use the public pip package.
COPY --chown=user /dist ./dist/
RUN python -m pip install --find-links=dist lilac

COPY --chown=user .env .
COPY --chown=user .env.demo .
# Copy the README so we can read the datasets from the HuggingFace config.
COPY --chown=user README.md .
# Copy the license just in case.
COPY --chown=user LICENSE .

COPY --chown=user docker_start.sh docker_start.py ./

# Make a local data directory for non-persistent storage demos.
RUN mkdir -p ./data
RUN chown -R user ./data

CMD ["bash", "docker_start.sh"]
