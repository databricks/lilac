# Tests the FastAPI server when it is mounted as a sub-path.

MOUNT_PATH='lilac_sub'

# Find a free port.
PORT=$(python -c 'import socket; s=socket.socket(); s.bind(("", 0)); print(s.getsockname()[1]); s.close()');

poetry run uvicorn integration_tests.fastapi_integration:app --port $PORT &
pid="$!"


URL="http://localhost:$PORT/"
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


curl --fail --silent "http://localhost:$PORT/lilac_sub/api/v1/tasks/"

curl --fail --silent "http://localhost:$PORT/lilac_sub/"
