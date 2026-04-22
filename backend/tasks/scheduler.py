from celery_app import celery_app
import asyncio

from core.logger import setup_logger
from database_celery import get_session
from services.sync import schedule_all_users

logger = setup_logger(__name__, 'sheduler.log')

async def _schedule():
    session = await get_session()
    logger.info(f"Создали сессию: {session}")
    try:
        await schedule_all_users(session)
        await session.commit()
        logger.info(f"Комит выполнен")
    except Exception as e:
        await session.rollback()
        logger.error(f"Возникла ошибка: {e}")
        raise
    finally:
        await session.close()

@celery_app.task(name="tasks.scheduler.schedule_sync", rate_limit="5/m")
def schedule_sync():
    logger.info("Начинаем планировщик")
    asyncio.run(_schedule())
