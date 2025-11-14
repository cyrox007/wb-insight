import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

def create_app() -> FastAPI:

    app = FastAPI()

    # Добавляем CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=['*'],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"]
    )

    # Подключаем статические файлы
    if not os.path.exists("static"):
        os.makedirs("static")
    app.mount("/static", StaticFiles(directory="static"), name="static")
    
    if not os.path.exists("uploads"):
        os.makedirs("uploads")
    app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

    return app

app = create_app()