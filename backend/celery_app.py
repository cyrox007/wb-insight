# celery_app.py

from celery import Celery
from celery.schedules import crontab
from settings import config
import models

celery_app = Celery(
    "wb_analytics",
    broker=config.CELERY_BROKER_URL,
    backend=config.CELERY_RESULT_BACKEND,
    include=[
        "tasks.scheduler",     # 👈 новый
        "tasks.processor",     # 👈 новый
    ]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Moscow",
    enable_utc=False,

    task_track_started=True,
    task_time_limit=30 * 60,
    task_soft_time_limit=25 * 60,

    worker_concurrency=2,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,

    # важно для стабильности
    task_acks_late=True,
    worker_max_tasks_per_child=100,
)

# ❗ ЕДИНСТВЕННЫЙ SCHEDULER
celery_app.conf.beat_schedule = {
    "wb-global-sync-scheduler": {
        "task": "tasks.scheduler.schedule_sync",
        "schedule": 60.0,  # каждую минуту проверяем
    },
}