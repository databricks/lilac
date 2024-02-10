import lilac.server
import uvicorn
from fastapi import FastAPI

app = FastAPI()


@app.get('/')
def read_main():
  return {'message': 'Hello World from main app'}


app.mount('/lilac', lilac.server.app)

if __name__ == '__main__':
  uvicorn.run(app, host='0.0.0.0', port=8000)
