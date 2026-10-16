# celery_app.py

import os

from celery import Celery

import models
from core.lifecycle_config import lifecycle_config
from core.ops_config import ops_config
from settings import config


# На сервере Redis разделяют несколько проектов. У WB должны быть собственные
# очередь и служебные ключи, иначе чужой worker может забрать и отбросить задачу.
CELERY_QUEUE_NAME = os.getenv("CELERY_QUEUE_NAME", "wb-insight.celery").strip()
CELERY_REDIS_KEY_PREFIX = os.getenv(
    "CELERY_REDIS_KEY_PREFIX", "wb-insight:celery:"
).strip()

if not CELERY_QUEUE_NAME:
    raise RuntimeError("CELERY_QUEUE_NAME не может быть пустым")
if not CELERY_REDIS_KEY_PREFIX:
    raise RuntimeError("CELERY_REDIS_KEY_PREFIX не может быть пустым")

celery_app = Celery(
    "wb_analytics",
    broker=config.CELERY_BROKER_URL,
    backend=config.CELERY_RESULT_BACKEND,
    include=[
        "tasks.schedulers.create_state_scheduler",
        "tasks.schedulers.state_scheduler",
        "tasks.processors.job_processor",
        "tasks.processors.operations_monitor",
        "tasks.processors.mail_delivery",
    ],
)

mail_delivery_enabled = (
    lifecycle_config.MAIL_DELIVERY_ENABLED
    or lifecycle_config.PASSWORD_RESET_ENABLED
    or lifecycle_config.EMAIL_VERIFICATION_ENABLED
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
    worker_concurrency=1,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    task_acks_late=True,
    worker_max_tasks_per_child=100,
    mail_delivery_enabled=mail_delivery_enabled,
    task_default_queue=CELERY_QUEUE_NAME,
    task_default_exchange=CELERY_QUEUE_NAME,
    task_default_routing_key=CELERY_QUEUE_NAME,
    task_routes={"*": {"queue": CELERY_QUEUE_NAME, "routing_key": CELERY_QUEUE_NAME}},
    broker_transport_options={"global_keyprefix": CELERY_REDIS_KEY_PREFIX},
    result_backend_transport_options={"global_keyprefix": CELERY_REDIS_KEY_PREFIX},
)


def _scheduled_task(task: str, schedule: float) -> dict:
    """Создаёт расписание, жёстко привязанное к очереди WB."""
    return {
        "task": task,
        "schedule": schedule,
        "options": {
            "queue": CELERY_QUEUE_NAME,
            "routing_key": CELERY_QUEUE_NAME,
        },
    }


celery_app.conf.beat_schedule = {
    "wb-due-sync-scheduler": _scheduled_task(
        "tasks.schedulers.state_scheduler.schedule_sync", 60.0
    ),
    "wb-sync-state-discovery": _scheduled_task(
        "tasks.schedulers.create_state_scheduler.schedule_sync", 600.0
    ),
    "wb-job-processor": _scheduled_task("tasks.processors.job_processor.run", 300.0),
    "operations-monitor": _scheduled_task(
        "tasks.processors.operations_monitor.run",
        float(ops_config.ALERT_CHECK_INTERVAL_SECONDS),
    ),
    "mail-campaign-scheduler": _scheduled_task("mail.campaign.scan", 30.0),
    "mail-delivery": _scheduled_task("mail.delivery.scan", 15.0),
}
