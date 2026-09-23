"""Regression-контракт отсутствия публичной legacy-заглушки пользователей."""

from app import app


def test_public_legacy_users_route_is_not_exposed():
    """Публичный no-op маршрут пользователей не должен возвращаться в API."""
    paths = app.openapi()["paths"]

    assert "/users" not in paths
    assert "/users/" not in paths
