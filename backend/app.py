import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import models
from core.audit import AuditMiddleware
from core.http_metrics import HTTPMetricsMiddleware
from core.session_security import SessionSecurityMiddleware
from core.version import APP_VERSION
from handlers.account_lifecycle_handler import account_router, auth_router as account_auth_router
from handlers.auth_handler import router as auth_router
from handlers.control_panel.home import router as CP_home_router
from handlers.control_panel.operations import router as CP_operations_router
from handlers.control_panel.roles import router as CP_roles_router
from handlers.control_panel.tariffs import router as CP_tariffs_router
from handlers.control_panel.users import router as CP_users_router
from handlers.dashboard.ads_handler import router as D_ads_router
from handlers.dashboard.biling_handler import router as D_biling_handler_router
from handlers.dashboard.cost_price_handler import router as D_cost_price_router
from handlers.dashboard.expense_handler import router as D_expense_router
from handlers.dashboard.finance_handler import router as D_finance_router
from handlers.dashboard.inventory_handler import router as D_inventory_router
from handlers.dashboard.main_handler import router as D_main_router
from handlers.dashboard.prices_handler import router as D_prices_router
from handlers.dashboard.profile_handler import router as D_user_profile_router
from handlers.dashboard.subscription_handler import router as D_subscription_router
from handlers.dashboard.tariffs_handler import router as D_tariffs_router
from handlers.dashboard.token_handler import router as D_tokens_router
from handlers.dashboard.unit_economy_handler import router as D_unit_economy_router
from handlers.health_handler import router as health_router
from handlers.legal_handler import router as legal_router
from handlers.session_handler import router as session_router
from handlers.users_handler import routers as user_router
from settings import config


ALLOWED_ORIGINS = config.get_allowed_origins
ALLOWED_METHODS = ["GET", "POST", "PUT", "DELETE"]
STATIC_DIRECTORIES = {
    "static": "/static",
    "uploads": "/uploads",
}


def _setup_cors(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=ALLOWED_METHODS,
        allow_headers=["*"],
    )


def _setup_static_files(app: FastAPI) -> None:
    for dir_name, mount_path in STATIC_DIRECTORIES.items():
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)
        app.mount(mount_path, StaticFiles(directory=dir_name), name=dir_name)


def _register_routers(app: FastAPI) -> None:
    routers = [
        health_router,
        legal_router,
        user_router,
        auth_router,
        account_auth_router,
        account_router,
        session_router,
        D_main_router,
        D_user_profile_router,
        D_tariffs_router,
        D_subscription_router,
        D_tokens_router,
        D_biling_handler_router,
        D_unit_economy_router,
        D_ads_router,
        D_inventory_router,
        D_prices_router,
        D_finance_router,
        D_expense_router,
        D_cost_price_router,
        CP_home_router,
        CP_users_router,
        CP_tariffs_router,
        CP_roles_router,
        CP_operations_router,
    ]
    for router in routers:
        app.include_router(router)


def create_app() -> FastAPI:
    app = FastAPI(
        title="WB Insight API",
        description="Seller analytics API for WB Insight",
        version=APP_VERSION,
    )

    app.add_middleware(HTTPMetricsMiddleware)
    app.add_middleware(SessionSecurityMiddleware)
    app.add_middleware(AuditMiddleware)
    _setup_cors(app)
    _setup_static_files(app)
    _register_routers(app)
    return app


app = create_app()
