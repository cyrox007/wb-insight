# tasks/scheduler.py

from celery_app import celery_app
import asyncio


@celery_app.task(name="tasks.scheduler.schedule_sync")
def schedule_sync():
    asyncio.run(_schedule())


async def _schedule():
    from database import Database
    from services.sync import schedule_all_users

    # async with Database.get_session() as db:
    session = await Database.get_session()
    try:
        await schedule_all_users(session)
    finally:
        await session.close()