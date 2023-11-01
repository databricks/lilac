"""Writes the openapi.json file to the specified output.

This is meant to run as a standalone script. It lives in lilac/ so we can import the FastAPI app.
"""
import json

import click
from fastapi.openapi.utils import get_openapi

from .server import app


@click.command()
@click.option(
  '--output', required=True, type=str, help='The output filepath for the opepnapi.json file.'
)
def main(output: str) -> None:
  """Create the openapi.json file for the API to generate TypeScript stubs."""
  with open(output, 'w') as f:
    json.dump(
      get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        separate_input_output_schemas=False,
        description=app.description,
        routes=app.routes,
      ),
      f,
    )


if __name__ == '__main__':
  main()
