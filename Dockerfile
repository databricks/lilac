# NOTE: When we upgrade to 3.11 we can use a slimmer docker image which comes with gcc.
FROM python:3.9-bullseye

# Allow statements and log messages to immediately appear in the Knative logs
ENV PYTHONUNBUFFERED True

# Set the working directory in the container.
WORKDIR /server

# Install the dependencies. This requires exporting requirements.txt from poetry first, which
# happens from ./build_docker.sh.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the data to /data, the HF persistent storage. We do this after pip install to avoid
# re-installing dependencies if the data changes, which is likely more often.
WORKDIR /
COPY /data /data
WORKDIR /server

COPY .env .
COPY LICENSE .

# Copy static files.
COPY /web/blueprint/build ./web/blueprint/build

# Copy python files.
COPY /src ./src/

CMD ["uvicorn", "src.server:app", "--host", "0.0.0.0", "--port", "5432"]
