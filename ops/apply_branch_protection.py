#!/usr/bin/env python3
"""Применение и проверка branch protection для dev/main WB Insight.

Скрипт намеренно не хранит GitHub token в аргументах или файлах. Для изменения
правил нужен token владельца/администратора репозитория с правом Administration.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


API_VERSION = "2022-11-28"
DEFAULT_REPOSITORY = "cyrox007/wb-insight"


@dataclass(frozen=True)
class BranchPolicy:
    branch: str
    required_contexts: tuple[str, ...]


POLICIES = (
    BranchPolicy(
        branch="dev",
        required_contexts=("branch-policy",),
    ),
    BranchPolicy(
        branch="main",
        required_contexts=(
            "branch-policy",
            "build",
            "security-tests",
            "alembic-upgrade",
            "backup-restore",
            "docker-build",
            "acceptance-tools",
            "version",
            "validate",
            "smoke-contract",
        ),
    ),
)


class ProtectionError(RuntimeError):
    """Безопасная ошибка применения или проверки правил ветки."""


def _token() -> str:
    value = str(os.getenv("GH_ADMIN_TOKEN") or os.getenv("GITHUB_TOKEN") or "").strip()
    if not value:
        raise ProtectionError(
            "Не задан GH_ADMIN_TOKEN. Нужен GitHub token с правом Administration на репозиторий."
        )
    return value


def _request(
    repository: str,
    path: str,
    *,
    token: str,
    method: str = "GET",
    body: dict | None = None,
) -> dict:
    url = f"https://api.github.com/repos/{repository}{path}"
    payload = None
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": API_VERSION,
        "User-Agent": "wb-insight-branch-protection",
    }
    if body is not None:
        payload = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = Request(url, data=payload, headers=headers, method=method)
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        if exc.code in {401, 403}:
            raise ProtectionError(
                "GitHub отклонил административный запрос. Проверьте право Administration у token."
            ) from exc
        if exc.code == 404:
            raise ProtectionError(
                "GitHub не нашёл репозиторий/ветку либо token не имеет к ним доступа."
            ) from exc
        raise ProtectionError(f"GitHub API вернул HTTP {exc.code}.") from exc
    except URLError as exc:
        raise ProtectionError("Не удалось подключиться к GitHub API.") from exc

    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProtectionError("GitHub API вернул некорректный JSON.") from exc
    if not isinstance(value, dict):
        raise ProtectionError("GitHub API вернул неожиданный формат ответа.")
    return value


def _payload(policy: BranchPolicy) -> dict:
    return {
        "required_status_checks": {
            "strict": True,
            "contexts": list(policy.required_contexts),
        },
        "enforce_admins": True,
        "required_pull_request_reviews": {
            "dismiss_stale_reviews": True,
            "require_code_owner_reviews": False,
            "required_approving_review_count": 1,
            "require_last_push_approval": False,
        },
        "restrictions": None,
        "required_linear_history": False,
        "allow_force_pushes": False,
        "allow_deletions": False,
        "block_creations": False,
        "required_conversation_resolution": True,
        "lock_branch": False,
        "allow_fork_syncing": True,
    }


def _enabled(value: object) -> bool:
    if isinstance(value, dict):
        return value.get("enabled") is True
    return value is True


def _contexts(protection: dict) -> set[str]:
    status_checks = protection.get("required_status_checks") or {}
    values = status_checks.get("contexts") or []
    return {str(item) for item in values if item}


def _verify(policy: BranchPolicy, protection: dict) -> list[str]:
    problems: list[str] = []
    status_checks = protection.get("required_status_checks") or {}
    if status_checks.get("strict") is not True:
        problems.append("обязательные проверки не требуют актуальную ветку")

    actual_contexts = _contexts(protection)
    missing = sorted(set(policy.required_contexts) - actual_contexts)
    if missing:
        problems.append("не обязательны проверки: " + ", ".join(missing))

    reviews = protection.get("required_pull_request_reviews") or {}
    if int(reviews.get("required_approving_review_count") or 0) < 1:
        problems.append("не требуется одобрение pull request")
    if reviews.get("dismiss_stale_reviews") is not True:
        problems.append("устаревшие одобрения не сбрасываются")

    if not _enabled(protection.get("enforce_admins")):
        problems.append("правила не применяются к администраторам")
    if _enabled(protection.get("allow_force_pushes")):
        problems.append("разрешён force-push")
    if _enabled(protection.get("allow_deletions")):
        problems.append("разрешено удаление ветки")
    if not _enabled(protection.get("required_conversation_resolution")):
        problems.append("не требуется разрешение review-обсуждений")
    return problems


def apply_policy(repository: str, policy: BranchPolicy, token: str) -> None:
    branch = quote(policy.branch, safe="")
    _request(
        repository,
        f"/branches/{branch}/protection",
        token=token,
        method="PUT",
        body=_payload(policy),
    )
    print(f"Защита ветки {policy.branch} применена.")


def verify_policy(repository: str, policy: BranchPolicy, token: str) -> None:
    branch = quote(policy.branch, safe="")
    protection = _request(
        repository,
        f"/branches/{branch}/protection",
        token=token,
    )
    problems = _verify(policy, protection)
    if problems:
        joined = "; ".join(problems)
        raise ProtectionError(f"Ветка {policy.branch} защищена не полностью: {joined}.")
    print(f"Защита ветки {policy.branch} подтверждена.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Применить или проверить обязательные правила dev/main."
    )
    parser.add_argument(
        "--repository",
        default=os.getenv("GITHUB_REPOSITORY", DEFAULT_REPOSITORY),
        help="Репозиторий в формате owner/name.",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--apply", action="store_true", help="Применить правила.")
    mode.add_argument("--verify", action="store_true", help="Только проверить правила.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repository = str(args.repository or "").strip()
    if repository.count("/") != 1:
        raise ProtectionError("Репозиторий должен быть указан в формате owner/name.")

    token = _token()
    if args.apply:
        for policy in POLICIES:
            apply_policy(repository, policy, token)

    for policy in POLICIES:
        verify_policy(repository, policy, token)
    print("Правила dev/main соответствуют release governance WB Insight.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProtectionError as exc:
        print(f"Ошибка branch protection: {exc}", file=sys.stderr)
        raise SystemExit(1)
