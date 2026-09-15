# WB Insight — Release Readiness

Дата ревизии: 15 сентября 2026 года.

Текущий `main`: `0.9.0-alpha.4`. P28 готовится как `0.9.0-alpha.5`.

P22–P27 закрыты по коду. P28 закрывает хранение access JWT только в памяти, восстановление сессии через HttpOnly refresh-cookie и формальный release smoke.

После green merge P28 переход в `0.9.0-beta.1` разрешён только после feature freeze и успешного production-like core smoke.

До `1.0.0-rc.1` дополнительно должны быть подтверждены реальные WB/Sber smoke, production deployment/TLS, monitoring, off-host backup/restore drill и утверждённые non-draft legal documents.

`1.0.0` — первый публичный stable WB Web v1.

Подробные gates и smoke contract: `docs/VERSIONING.md` и `docs/RELEASE_SMOKE.md`.
