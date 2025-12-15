import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

def create_app() -> FastAPI:
    from handlers.users import routers as user_router
    from handlers.auth import router as auth_router
    from handlers.dashboard import router as dashboard_router

    app = FastAPI()
    
    # Добавляем CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=['http://localhost:5173'],
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

    app.include_router(user_router)
    app.include_router(auth_router)
    app.include_router(dashboard_router)

    return app

app = create_app()