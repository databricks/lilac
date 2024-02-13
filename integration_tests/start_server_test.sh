# Tests that the lilac server starts from the CLI.

set -e # Fail if any of the commands below fail.

# Make sure the CLI succeeds for test_data.
mkdir -p test_data
touch test_data/lilac.yml

# Find a free port.
PORT=$(python -c 'import socket; s=socket.socket(); s.bind(("", 0)); print(s.getsockname()[1]); s.close()');


poetry run lilac start ./test_data --port $PORT &
pid="$!"

URL="http://localhost:$PORT/docs"
start_time="$(date -u +%s)"
TIMEOUT_SEC=15
until curl --fail --silent "$URL" > /dev/null; do
  sleep 1
  current_time="$(date -u +%s)"
  elapsed_seconds=$(($current_time-$start_time))
  if [ $elapsed_seconds -gt $TIMEOUT_SEC ]; then
    echo "Timeout $TIMEOUT_SEC seconds to reach server."
    kill $pid
    exit 1
  fi
done

echo "GET request to $URL succeeded."

kill $pid
