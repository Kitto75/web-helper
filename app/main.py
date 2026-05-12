from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from .routes import router
from .db import init_db

app = FastAPI(title='3x-ui Admin Panel')
app.mount('/static', StaticFiles(directory='app/static'), name='static')
app.include_router(router)

@app.on_event('startup')
def startup():
    init_db()
