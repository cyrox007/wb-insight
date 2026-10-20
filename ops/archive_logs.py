#!/usr/bin/env python3
"""Архивирует неизменяемые журналы WB Insight без удаления исходных записей."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import sys
import tempfile
from datetime import date, datetime, time, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable
from uuid import UUID



SUPPORTED_TABLES = {
    "audit": "audit_events",
    "operations": "operation_log_events",
}
ARCHIVE_SCHEMA_VERSION = 1
DEFAULT_BATCH_SIZE = 1000


class LogArchiveError(RuntimeError):
    """Ошибка безопасного архивирования журналов."""


def _parse_cutoff(value: str) -> datetime:
    normalized = str(value or "").strip()
    if not normalized:
        raise LogArchiveError("Не указана дата отсечения архива")

    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LogArchiveError(
            "Дата отсечения должна быть в формате ISO 8601 с часовым поясом"
        ) from exc

    if parsed.tzinfo is None:
        raise LogArchiveError(
            "Дата отсечения должна содержать часовой пояс, например +00:00"
        )
    return parsed.astimezone(timezone.utc)


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return str(value)


def _database_connection_kwargs() -> dict[str, Any]:
    password = os.getenv("DB_PASSWORD")
    if password is None:
        raise LogArchiveError("Переменная DB_PASSWORD не задана")

    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "5432")),
        "dbname": os.getenv("DB_NAME", "wb"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": password,
        "connect_timeout": 10,
        "application_name": "wb-insight-log-archive",
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_archive_name(table: str, cutoff: datetime) -> str:
    suffix = cutoff.strftime("%Y%m%dT%H%M%SZ")
    return f"{table}-before-{suffix}.jsonl.gz"


def _open_secure_gzip(path: Path):
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    file_descriptor = os.open(path, flags, 0o600)
    raw = os.fdopen(file_descriptor, "wb")
    compressed = gzip.GzipFile(fileobj=raw, mode="wb", mtime=0)
    return raw, compressed, io.TextIOWrapper(compressed, encoding="utf-8", newline="\n")


def _write_rows(
    path: Path,
    rows: Iterable[dict[str, Any]],
) -> tuple[int, str | None, str | None]:
    row_count = 0
    first_created_at: str | None = None
    last_created_at: str | None = None
    raw = None
    compressed = None
    text_stream = None

    try:
        raw, compressed, text_stream = _open_secure_gzip(path)
        for row in rows:
            payload = _json_value(dict(row))
            created_at = str(payload.get("created_at") or "") or None
            if first_created_at is None:
                first_created_at = created_at
            last_created_at = created_at
            text_stream.write(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
            text_stream.write("\n")
            row_count += 1

        text_stream.flush()
        compressed.flush()
        raw.flush()
        os.fsync(raw.fileno())
    finally:
        if text_stream is not None:
            text_stream.close()
        elif compressed is not None:
            compressed.close()
        elif raw is not None:
            raw.close()

    return row_count, first_created_at, last_created_at


def _iter_table_rows(
    connection,
    *,
    table: str,
    cutoff: datetime,
    batch_size: int,
    cursor_factory,
):
    cursor_name = f"archive_{table}_{os.getpid()}"
    with connection.cursor(name=cursor_name, cursor_factory=cursor_factory) as cursor:
        cursor.itersize = batch_size
        cursor.execute(
            f'SELECT * FROM "{table}" WHERE created_at < %s '
            "ORDER BY created_at ASC, id ASC",
            (cutoff,),
        )
        while True:
            rows = cursor.fetchmany(batch_size)
            if not rows:
                break
            yield from rows


def _verify_archive_file(
    path: Path,
    *,
    expected_rows: int,
    cutoff: datetime,
) -> None:
    actual_rows = 0
    try:
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                try:
                    payload = json.loads(raw_line)
                except json.JSONDecodeError as exc:
                    raise LogArchiveError(
                        f"Архив {path.name} повреждён на строке {line_number}"
                    ) from exc

                created_at_raw = payload.get("created_at")
                if not created_at_raw:
                    raise LogArchiveError(
                        f"Архив {path.name} содержит запись без created_at"
                    )
                created_at = _parse_cutoff(str(created_at_raw))
                if created_at >= cutoff:
                    raise LogArchiveError(
                        f"Архив {path.name} содержит запись новее даты отсечения"
                    )
                actual_rows += 1
    except OSError as exc:
        raise LogArchiveError(f"Не удалось прочитать архив {path.name}") from exc

    if actual_rows != expected_rows:
        raise LogArchiveError(
            f"Архив {path.name} содержит {actual_rows} записей вместо {expected_rows}"
        )


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".partial")
    if temporary.exists():
        raise LogArchiveError(
            f"Обнаружен незавершённый временный файл {temporary.name}"
        )

    file_descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _verify_manifest(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LogArchiveError("Манифест архива должен быть корректным UTF-8 JSON") from exc

    if not isinstance(payload, dict):
        raise LogArchiveError("Манифест архива должен содержать JSON-объект")
    if payload.get("schema_version") != ARCHIVE_SCHEMA_VERSION:
        raise LogArchiveError("Версия схемы манифеста архива не поддерживается")
    if payload.get("kind") != "wb_insight_log_archive":
        raise LogArchiveError("Манифест не относится к архиву журналов WB Insight")
    if payload.get("status") != "complete":
        raise LogArchiveError("Манифест не подтверждает завершённый архив")

    cutoff = _parse_cutoff(str(payload.get("cutoff") or ""))
    files = payload.get("files")
    if not isinstance(files, list) or not files:
        raise LogArchiveError("Манифест архива не содержит файлов")

    for item in files:
        if not isinstance(item, dict):
            raise LogArchiveError("Некорректная запись файла в манифесте")
        filename = str(item.get("filename") or "")
        expected_sha = str(item.get("sha256") or "")
        expected_rows = item.get("rows")
        if not filename or len(expected_sha) != 64 or not isinstance(expected_rows, int):
            raise LogArchiveError("Некорректные метаданные файла в манифесте")
        archive_path = path.parent / filename
        if not archive_path.is_file():
            raise LogArchiveError(f"Файл архива {filename} отсутствует")
        if _sha256(archive_path) != expected_sha:
            raise LogArchiveError(f"Контрольная сумма {filename} не совпадает")
        _verify_archive_file(
            archive_path,
            expected_rows=expected_rows,
            cutoff=cutoff,
        )

    return payload


def archive_logs(
    *,
    cutoff: datetime,
    output_dir: Path,
    kinds: tuple[str, ...],
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> Path:
    if batch_size < 1 or batch_size > 10000:
        raise LogArchiveError("Размер пакета должен быть от 1 до 10000 записей")

    unknown = [item for item in kinds if item not in SUPPORTED_TABLES]
    if unknown:
        raise LogArchiveError(
            "Неизвестный тип журнала: " + ", ".join(sorted(set(unknown)))
        )

    output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        os.chmod(output_dir, 0o700)
    except OSError:
        pass

    timestamp = datetime.now(timezone.utc)
    manifest_name = f"log-archive-{timestamp.strftime('%Y%m%dT%H%M%SZ')}.manifest.json"
    manifest_path = output_dir / manifest_name
    if manifest_path.exists():
        raise LogArchiveError(f"Манифест {manifest_name} уже существует")

    created_paths: list[Path] = []
    file_entries: list[dict[str, Any]] = []

    try:
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
        except ImportError as exc:
            raise LogArchiveError(
                "Для подключения к PostgreSQL требуется установленный psycopg2"
            ) from exc

        try:
            connection = psycopg2.connect(**_database_connection_kwargs())
        except psycopg2.Error as exc:
            raise LogArchiveError("Не удалось подключиться к PostgreSQL") from exc

        try:
            connection.set_session(readonly=True, autocommit=False)
            for kind in kinds:
                table = SUPPORTED_TABLES[kind]
                filename = _safe_archive_name(table, cutoff)
                final_path = output_dir / filename
                partial_path = output_dir / f"{filename}.partial"
                if final_path.exists() or partial_path.exists():
                    raise LogArchiveError(
                        f"Архив {filename} уже существует или не был завершён ранее"
                    )

                rows = _iter_table_rows(
                    connection,
                    table=table,
                    cutoff=cutoff,
                    batch_size=batch_size,
                    cursor_factory=RealDictCursor,
                )
                row_count, first_created_at, last_created_at = _write_rows(
                    partial_path,
                    rows,
                )
                _verify_archive_file(
                    partial_path,
                    expected_rows=row_count,
                    cutoff=cutoff,
                )
                os.replace(partial_path, final_path)
                created_paths.append(final_path)
                file_entries.append(
                    {
                        "kind": kind,
                        "table": table,
                        "filename": filename,
                        "rows": row_count,
                        "first_created_at": first_created_at,
                        "last_created_at": last_created_at,
                        "size_bytes": final_path.stat().st_size,
                        "sha256": _sha256(final_path),
                    }
                )
        finally:
            connection.close()

        manifest = {
            "schema_version": ARCHIVE_SCHEMA_VERSION,
            "kind": "wb_insight_log_archive",
            "status": "complete",
            "created_at": timestamp.isoformat(),
            "cutoff": cutoff.isoformat(),
            "source": "PostgreSQL read-only export",
            "deletion_performed": False,
            "files": file_entries,
        }
        _write_json_atomic(manifest_path, manifest)
        created_paths.append(manifest_path)
        _verify_manifest(manifest_path)
        return manifest_path
    except Exception:
        for path in created_paths:
            path.unlink(missing_ok=True)
        for path in output_dir.glob("*.partial"):
            path.unlink(missing_ok=True)
        raise


def _self_test() -> None:
    cutoff = datetime(2026, 1, 2, tzinfo=timezone.utc)
    assert _parse_cutoff("2026-01-02T00:00:00Z") == cutoff
    try:
        _parse_cutoff("2026-01-02T00:00:00")
    except LogArchiveError:
        pass
    else:
        raise AssertionError("Дата без часового пояса ошибочно принята")

    with tempfile.TemporaryDirectory() as temporary_dir:
        directory = Path(temporary_dir)
        archive = directory / "audit_events-before-20260102T000000Z.jsonl.gz"
        rows = [
            {
                "id": UUID("00000000-0000-0000-0000-000000000001"),
                "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
                "metadata": {"amount": Decimal("10.50")},
            }
        ]
        count, first_seen, last_seen = _write_rows(archive, rows)
        assert count == 1
        assert first_seen == last_seen == "2026-01-01T00:00:00+00:00"
        _verify_archive_file(archive, expected_rows=1, cutoff=cutoff)

        manifest = directory / "self-test.manifest.json"
        _write_json_atomic(
            manifest,
            {
                "schema_version": ARCHIVE_SCHEMA_VERSION,
                "kind": "wb_insight_log_archive",
                "status": "complete",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "cutoff": cutoff.isoformat(),
                "source": "self-test",
                "deletion_performed": False,
                "files": [
                    {
                        "kind": "audit",
                        "table": "audit_events",
                        "filename": archive.name,
                        "rows": 1,
                        "first_created_at": first_seen,
                        "last_created_at": last_seen,
                        "size_bytes": archive.stat().st_size,
                        "sha256": _sha256(archive),
                    }
                ],
            },
        )
        _verify_manifest(manifest)

    print("[ok] Самопроверка архивирования журналов завершена")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--before",
        help="Архивировать записи строго старше этой даты ISO 8601 с часовым поясом",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(os.getenv("LOG_ARCHIVE_DIR", "/var/backups/wb/log-archive")),
        help="Каталог для архивов и манифеста",
    )
    parser.add_argument(
        "--kind",
        choices=["all", *SUPPORTED_TABLES],
        default="all",
        help="Какой журнал архивировать",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="Размер серверного пакета чтения из PostgreSQL",
    )
    parser.add_argument(
        "--verify-manifest",
        type=Path,
        help="Проверить существующий манифест и контрольные суммы без обращения к БД",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Выполнить локальную самопроверку без подключения к БД",
    )
    args = parser.parse_args()

    if args.self_test:
        _self_test()
        return 0

    if args.verify_manifest is not None:
        _verify_manifest(args.verify_manifest.resolve())
        print(f"[ok] Архив подтверждён: {args.verify_manifest}")
        return 0

    if not args.before:
        raise LogArchiveError("Для создания архива требуется параметр --before")

    cutoff = _parse_cutoff(args.before)
    if cutoff >= datetime.now(timezone.utc):
        raise LogArchiveError("Дата отсечения должна находиться в прошлом")

    kinds = tuple(SUPPORTED_TABLES) if args.kind == "all" else (args.kind,)
    manifest_path = archive_logs(
        cutoff=cutoff,
        output_dir=args.output_dir.resolve(),
        kinds=kinds,
        batch_size=args.batch_size,
    )
    print(f"[ok] Архив создан и проверен: {manifest_path}")
    print("[ok] Исходные записи PostgreSQL не удалялись")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LogArchiveError as exc:
        print(f"[ошибка] {exc}", file=sys.stderr)
        raise SystemExit(1)
