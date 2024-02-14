"""Tests the FastAPI server can be mounted."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from .server import app as lilac_app

app = FastAPI()

MOUNT_POINT = '/lilac_sub'


@app.get('/')
def read_main() -> dict:
  """The main endpoint."""
  return {'message': 'hello world'}


app.mount(MOUNT_POINT, lilac_app)
client = TestClient(app)


def test_mount_root() -> None:
  response = client.get('/', allow_redirects=False)
  assert response.status_code == 200
  assert response.json() == {'message': 'hello world'}


def test_mount_slash_redirect() -> None:
  response = client.get(f'{MOUNT_POINT}/auth_info/', allow_redirects=False)
  assert response.status_code == 307
  # We should redirect to the URL with slash removed.
  assert response.headers['location'] == f'{MOUNT_POINT}/auth_info'

  # Allow redirects to follow through.
  response = client.get(f'{MOUNT_POINT}/auth_info/', allow_redirects=True)
  assert response.status_code == 200
