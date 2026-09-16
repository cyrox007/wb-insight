from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from settings import config as cfg

# Import all mapped models so Database.Base.metadata is complete for
# autogenerate/alembic check. Role permissions are code-defined and therefore
# intentionally have no SQLAlchemy model/table.
from models.users_model import User, UserRoleAssociation
from models.tariffs_model import TariffPlan, TariffLimit
from models.subscription_model import Subscription
from models.payments_model import Payment, PaymentEvent
from models.payment_provider_config import PaymentProviderConfig
from models.tokens_model import APIToken
from models.wb_report import WbRealizationReport
from models.wb_product import WbProduct
from models.wb_stock import WbStock
from models.wb_advertising_stats import WbAdvertisingStats
from models.wb_operational import WbOrder, WbSale
from models.wb_sales_funnel import WbSalesFunnelDaily
from models.wb_paid_storage import WbPaidStorage
from models.wb_price import WbPriceCurrent, WbPriceChange
from models.wb_finance_summary import WbFinanceReportSummary, WbFinanceBalanceCurrent
from models.sync_job_model import SyncJob
from models.user_sync_state_model import UserSyncState
from models.product_cost_price_model import ProductCostPrice
from models.product_cost_price_history import ProductCostPriceHistory
from models.manual_expense import ManualExpense
from models.monthly_revenue_plan import MonthlyRevenuePlan
from models.legal_consent import LegalConsent
from models.account_lifecycle import AccountLifecycleEvent, PasswordResetToken


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", cfg.database_url())
target_metadata = User.__table__.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
