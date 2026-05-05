import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

import models
from settings import config

from handlers.users_handler import routers as user_router
from handlers.auth_handler import router as auth_router
from handlers.dashboard.main_handler import router as D_main_router
from handlers.dashboard.profile_handler import router as D_user_profile_router
from handlers.dashboard.tariffs_handler import router as D_tariffs_router
from handlers.dashboard.subscription_handler import router as D_subscription_router
from handlers.dashboard.token_handler import router as D_tokens_router
from handlers.dashboard.biling_handler import router as D_biling_handler_router
from handlers.dashboard.unit_economy_handler import router as D_unit_economy_router
from handlers.control_panel.home import router as CP_home_router
from handlers.control_panel.users import router as CP_users_router
from handlers.control_panel.tariffs import router as CP_tariffs_router
from handlers.control_panel.roles import router as CP_roles_router


ALLOWED_ORIGINS = config.get_allowed_origins
ALLOWED_METHODS = ["GET", "POST", "PUT", "DELETE"]
STATIC_DIRECTORIES = {
    "static": "/static",
    "uploads": "/uploads"
}


def _setup_cors(app: FastAPI) -> None:
    """Настройка CORS middleware."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=ALLOWED_METHODS,
        allow_headers=["*"],
    )


def _setup_static_files(app: FastAPI) -> None:
    """Подключение статических файлов."""
    for dir_name, mount_path in STATIC_DIRECTORIES.items():
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)
        app.mount(mount_path, StaticFiles(directory=dir_name), name=dir_name)


def _register_routers(app: FastAPI) -> None:
    """Регистрация всех роутеров приложения."""
    routers = [
        user_router,
        auth_router,
        D_main_router,
        D_user_profile_router,
        D_tariffs_router,
        D_subscription_router,
        D_tokens_router,
        D_biling_handler_router,
        D_unit_economy_router,
        CP_home_router,
        CP_users_router,
        CP_tariffs_router,
        CP_roles_router,
    ]
    for router in routers:
        app.include_router(router)


def create_app() -> FastAPI:
    """Создание и настройка FastAPI приложения."""
    app = FastAPI(
        title="Wildberries Dashboard API",
        description="API для управления дашбордом Wildberries",
        version="1.0.0"
    )
    
    _setup_cors(app)
    _setup_static_files(app)
    _register_routers(app)
    
    return app


app = create_app()