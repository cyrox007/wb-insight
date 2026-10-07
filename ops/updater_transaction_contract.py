#!/usr/bin/env python3
"""Проверяет транзакционный контракт systemd-обновлятора без изменения host."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ContractError(RuntimeError):
    """Ошибка статического контракта обновлятора."""


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _require(text: str, marker: str, *, file_name: str) -> None:
    if marker not in text:
        raise ContractError(f"{file_name}: отсутствует обязательный контракт: {marker}")


def _require_before(
    text: str,
    first: str,
    second: str,
    *,
    file_name: str,
) -> None:
    _require(text, first, file_name=file_name)
    _require(text, second, file_name=file_name)
    if text.index(first) >= text.index(second):
        raise ContractError(
            f"{file_name}: нарушен порядок '{first}' перед '{second}'"
        )


def main() -> int:
    bootstrap = _read("update.sh")
    updater = _read("ops/update_systemd.sh")
    publisher = _read("ops/publish_frontend.sh")

    _require(bootstrap, "flock -n 9", file_name="update.sh")
    _require(
        bootstrap,
        'git -C "$PROJECT_DIR" show "$target_commit:ops/update_systemd.sh"',
        file_name="update.sh",
    )
    _require(
        bootstrap,
        'WB_UPDATE_PREVIOUS_COMMIT="$previous_commit"',
        file_name="update.sh",
    )
    _require(
        bootstrap,
        'WB_UPDATE_TARGET_COMMIT="$target_commit"',
        file_name="update.sh",
    )

    required_updater_markers = (
        'git -C "$PROJECT_DIR" archive "$TARGET_COMMIT"',
        'CANDIDATE_FRONTEND="$CANDIDATE_DIR/frontend"',
        "npm ci",
        "VITE_API_BASE_URL=/api npm run build",
        "stop_application_writers",
        "create_database_rollback_point",
        "DB_MUTATION_STARTED=true",
        '"$NEW_VENV/bin/python" -m alembic upgrade head',
        'git -C "$PROJECT_DIR" reset --hard "$TARGET_COMMIT"',
        'git -C "$PROJECT_DIR" reset --hard "$PREVIOUS_COMMIT"',
        "RESTORE_CONFIRM=YES",
        'FRONTEND_PUBLISH_STATE_FILE="$FRONTEND_STATE_FILE"',
        "rollback_update",
        "WB_UPDATE_FAIL_PHASE",
    )
    for marker in required_updater_markers:
        _require(updater, marker, file_name="ops/update_systemd.sh")

    execution = updater[updater.index("acquire_update_lock_if_needed\n\nlog ") :]
    _require_before(
        execution,
        "build_candidate_runtime",
        "stop_application_writers",
        file_name="ops/update_systemd.sh",
    )
    _require_before(
        execution,
        "create_database_rollback_point",
        "apply_candidate_migrations",
        file_name="ops/update_systemd.sh",
    )
    _require_before(
        execution,
        "apply_candidate_migrations",
        "switch_repository",
        file_name="ops/update_systemd.sh",
    )
    _require_before(
        execution,
        "wait_backend_ready",
        "publish_candidate_frontend",
        file_name="ops/update_systemd.sh",
    )

    _require(
        publisher,
        'BUILD_DIR="${FRONTEND_BUILD_DIR:-$FRONTEND_DIR/dist}"',
        file_name="ops/publish_frontend.sh",
    )
    _require(
        publisher,
        'FRONTEND_PUBLISH_STATE_FILE="${FRONTEND_PUBLISH_STATE_FILE:-}"',
        file_name="ops/publish_frontend.sh",
    )
    publish_execution = publisher[publisher.index('log "Публикация frontend в nginx root') :]
    _require_before(
        publish_execution,
        'run_root mv -- "$DEPLOY_DIR" "$PREVIOUS_DIR"',
        "OLD_MOVED=true",
        file_name="ops/publish_frontend.sh",
    )
    _require_before(
        publish_execution,
        "OLD_MOVED=true",
        'run_root mv -- "$STAGING_DIR" "$DEPLOY_DIR"',
        file_name="ops/publish_frontend.sh",
    )
    _require(
        publisher,
        'if [[ "$OLD_MOVED" == true',
        file_name="ops/publish_frontend.sh",
    )

    print("Транзакционный контракт обновлятора подтверждён.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
