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

# Install the dependencies. This requires exporting requirements.txt from poetry first, which
# happens from ./build_docker.sh.
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=user .env .
COPY --chown=user .env.demo .
# Copy the README so we can read the datasets from the HuggingFace config.
COPY --chown=user README.md .
COPY --chown=user LICENSE .

# Copy python files.
COPY --chown=user /lilac ./lilac/

COPY --chown=user docker_start.sh docker_start.py ./

# Make a local data directory for non-persistent storage demos.
RUN mkdir -p ./data
RUN chown -R user ./data

CMD ["bash", "docker_start.sh"]
