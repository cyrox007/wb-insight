# tasks/scheduler.py

from celery_app import celery_app
import asyncio
from asyncio import get_event_loop


@celery_app.task(name="tasks.scheduler.schedule_sync")
def schedule_sync():
    loop = get_event_loop()
    loop.run_until_complete(_schedule())


async def _schedule():
    from database import Database
    from services.sync import schedule_all_users

    # async with Database.get_session() as db:
    session = await Database.get_session()
    try:
        await schedule_all_users(session)
    finally:
        await session.close()