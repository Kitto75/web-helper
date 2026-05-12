from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .db import init_db
from .routes import router

app = FastAPI(title='3x-ui Admin Panel')

# Ensure static directory exists before mounting (helps first run on fresh clones).
static_dir = Path(__file__).resolve().parent / 'static'
static_dir.mkdir(parents=True, exist_ok=True)
app.mount('/static', StaticFiles(directory=str(static_dir)), name='static')

app.include_router(router)


@app.on_event('startup')
def startup():
    init_db()
