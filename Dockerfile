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

COPY .env .
COPY .env.demo .
COPY LICENSE .

# Copy python files.
COPY /lilac ./lilac/

# Copy the data files. We use glob so docker copy won't fail if the directory doesn't exist.
COPY /dat[a] ./data/

CMD [ \
  "gunicorn", "lilac.server:app", \
  "--bind", "0.0.0.0:5432", \
  "-k", "uvicorn.workers.UvicornWorker" \
  ]
