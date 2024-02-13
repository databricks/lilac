"""Integration tests where the FastAPI app is mounted."""
import lilac.server
from fastapi import FastAPI

app = FastAPI()


@app.get('/')
def read_main():
  """The main endpoint."""
  return {'message': 'Hello World from main app'}


app.mount('/lilac_sub', lilac.server.app)
