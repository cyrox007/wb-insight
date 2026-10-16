from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_celery_code_uses_project_namespace():
    source = (ROOT / "backend" / "celery_app.py").read_text(encoding="utf-8")

    assert '"wb-insight.celery"' in source
    assert '"wb-insight:celery:"' in source
    assert "task_default_queue=CELERY_QUEUE_NAME" in source
    assert "task_default_exchange=CELERY_QUEUE_NAME" in source
    assert "task_default_routing_key=CELERY_QUEUE_NAME" in source
    assert 'task_routes={"*": {"queue": CELERY_QUEUE_NAME' in source
    assert 'broker_transport_options={"global_keyprefix": CELERY_REDIS_KEY_PREFIX}' in source
    assert 'result_backend_transport_options={"global_keyprefix": CELERY_REDIS_KEY_PREFIX}' in source


def test_systemd_worker_consumes_only_wb_queue():
    worker = (
        ROOT / "ops" / "systemd" / "wb-celery.service.d" / "10-wb-insight.conf"
    ).read_text(encoding="utf-8")
    beat = (
        ROOT / "ops" / "systemd" / "wb-celery-beat.service.d" / "10-wb-insight.conf"
    ).read_text(encoding="utf-8")

    assert "--queues=wb-insight.celery" in worker
    assert 'Environment="CELERY_QUEUE_NAME=wb-insight.celery"' in worker
    assert 'Environment="CELERY_REDIS_KEY_PREFIX=wb-insight:celery:"' in worker
    assert 'Environment="CELERY_QUEUE_NAME=wb-insight.celery"' in beat
    assert 'Environment="CELERY_REDIS_KEY_PREFIX=wb-insight:celery:"' in beat


def test_compose_worker_consumes_only_wb_queue():
    compose = (ROOT / "compose.production.yml").read_text(encoding="utf-8")

    assert "--queues=wb-insight.celery" in compose
    assert "CELERY_QUEUE_NAME: wb-insight.celery" in compose
    assert 'CELERY_REDIS_KEY_PREFIX: "wb-insight:celery:"' in compose
