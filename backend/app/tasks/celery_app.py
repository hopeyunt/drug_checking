from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "drugcheck",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.interaction_tasks",
        "app.tasks.loyalty_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Europe/Moscow",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

celery_app.conf.beat_schedule = {
    # Каждый 1-й день месяца в 00:00 — пересчёт уровней лояльности
    "recalculate-loyalty-monthly": {
        "task": "app.tasks.loyalty_tasks.recalculate_all_loyalty_levels",
        "schedule": crontab(hour=0, minute=0, day_of_month=1),
    },
}
