# Bash-based integration tests for lilac.

set -e # Fail if any of the commands below fail.

# Make sure the CLI succeeds for test_data.
mkdir -p test_data
touch test_data/lilac.yml

FREE_PORT=$(python -c 'import socket; s=socket.socket(); s.bind(("", 0)); print(s.getsockname()[1]); s.close()');


poetry run lilac start ./test_data --port $FREE_PORT &
pid="$!" # need to get the pid of the vlc process.
sleep 4

# Make a test request using curl
curl --fail "http://localhost:$FREE_PORT/docs"

# Save curl's exit code (-f option causes it to return one on HTTP errors)
curl_exit_code=$?

kill $pid

exit 0
