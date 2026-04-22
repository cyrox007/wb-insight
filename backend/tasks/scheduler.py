# tasks/scheduler.py

from celery_app import celery_app
from asyncio import get_event_loop


@celery_app.task(name="tasks.scheduler.schedule_sync")
def schedule_sync():
    loop = get_event_loop()
    loop.run_until_complete(_schedule())


async def _schedule():
    from database_celery import get_session
    from services.sync import schedule_all_users

    # async with Database.get_session() as db:
    session = await get_session()
    try:
        await schedule_all_users(session)
    finally:
        await session.close()