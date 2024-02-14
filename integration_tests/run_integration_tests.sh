# Bash-based integration tests for lilac.

set -e # Fail if any of the commands below fail.

./integration_tests/start_server_test.sh

echo
echo "CLI integration tests passed."
exit 0
