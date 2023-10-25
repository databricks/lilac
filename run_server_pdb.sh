#!/bin/bash

export LILAC_PROJECT_DIR='./data'
poetry run python -c "import lilac.server; import uvicorn; uvicorn.run(lilac.server.app, host='0.0.0.0', port=5173)"
