# celery_app.py

from celery import Celery

import models
from core.lifecycle_config import lifecycle_config
from core.ops_config import ops_config
from settings import config


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
)

celery_app.conf.beat_schedule = {
    "wb-global-sync-scheduler": {"task": "tasks.schedulers.state_scheduler.schedule_sync", "schedule": 60.0},
    "wb-global-sync-scheduler-2": {"task": "tasks.schedulers.create_state_scheduler.schedule_sync", "schedule": 600.0},
    "wb-job-worker": {"task": "tasks.processors.job_processor.run", "schedule": 300.0},
    "operations-monitor": {"task": "tasks.processors.operations_monitor.run", "schedule": float(ops_config.ALERT_CHECK_INTERVAL_SECONDS)},
    "mail-campaign-scheduler": {"task": "mail.campaign.scan", "schedule": 30.0},
    "mail-delivery": {"task": "mail.delivery.scan", "schedule": 15.0},
}
