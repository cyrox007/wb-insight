#!/usr/bin/env python3
"""Проверяет, что exact-head CI запускается на каждом push в release-ветки."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

WORKFLOWS = (
    ".github/workflows/backend-security.yml",
    ".github/workflows/frontend-build.yml",
    ".github/workflows/database-migrations.yml",
    ".github/workflows/release-integrity.yml",
    ".github/workflows/release-smoke-contract.yml",
    ".github/workflows/systemd-updater.yml",
)


def _push_section(text: str) -> str:
    marker = "  push:\n"
    start = text.find(marker)
    if start < 0:
        raise AssertionError("В workflow отсутствует trigger push")
    end = text.find("\n\nconcurrency:", start)
    if end < 0:
        raise AssertionError("Не удалось определить секцию push workflow")
    return text[start:end]


def main() -> int:
    for relative_path in WORKFLOWS:
        text = (ROOT / relative_path).read_text(encoding="utf-8")
        section = _push_section(text)
        if "    paths:" in section or "    paths-ignore:" in section:
            raise AssertionError(
                f"Exact-head workflow ограничен путями на push: {relative_path}"
            )
        if "dev" not in section or "main" not in section:
            raise AssertionError(
                f"Exact-head workflow не запускается для dev/main: {relative_path}"
            )

    print("[ok] exact-head CI запускается на каждом push в dev/main")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
