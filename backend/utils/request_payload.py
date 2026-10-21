"""Безопасное чтение JSON-объектов из HTTP-запросов."""

from fastapi import Request


async def request_json_object(request: Request) -> dict | None:
    """Возвращает JSON-объект или None для битого JSON и других JSON-типов."""
    try:
        payload = await request.json()
    except (TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None
