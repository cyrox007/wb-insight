import os
from celery import Celery
from celery.schedules import crontab
from settings import config

# Инициализация Celery
celery_app = Celery(
    "wb_analytics",
    broker=config.CELERY_BROKER_URL,
    backend=config.CELERY_RESULT_BACKEND,
    include=[
        "tasks.wb_sync",
        "tasks.reports",
    ]
)

# Базовые настройки
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Moscow",
    enable_utc=False,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 минут максимум на задачу
    task_soft_time_limit=25 * 60,  # 25 минут до мягкого таймаута
    worker_prefetch_multiplier=1,  # Важно для долгих задач!
    broker_connection_retry_on_startup=True,
)

# Периодические задачи (расписание)
celery_app.conf.beat_schedule = {
    # Синхронизация реализации (финансы) — раз в 4 часа
    "sync-wb-realization-every-4h": {
        "task": "tasks.wb_sync.sync_wb_realization",
        "schedule": crontab(minute=0, hour="*/4"),
    },
    
    # Синхронизация рекламы — раз в 6 часов (данные обновляются реже)
    "sync-wb-ad-stats-every-6h": {
        "task": "tasks.wb_sync.sync_wb_ad_stats",
        "schedule": crontab(minute=30, hour="*/6"),
    },
    
    # Ежедневная агрегация отчётов в 02:00 МСК
    "daily-report-aggregation": {
        "task": "tasks.reports.generate_daily_reports",
        "schedule": crontab(hour=2, minute=0),
    },
    
    # Проверка истекающих токенов за 7 дней до окончания
    "check-expiring-tokens": {
        "task": "tasks.wb_sync.check_expiring_tokens",
        "schedule": crontab(hour=9, minute=0),  # Каждый день в 09:00
    },
}

# Для работы с асинхронными задачами (опционально)
@celery_app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")