# P35 — hardening обязательного data-accuracy coverage

**Статус:** закрыт.  
**PR:** #56  
**Merge:** `d2e782208228fbe60cb92b9e61fbf8d325f0e839`  
**Product baseline:** `0.9.0-alpha.11`.

P35 закрыл обход beta data-accuracy gate, при котором входной acceptance dataset мог не включать policy-required метрики или расширять tolerance без фиксированной причины.

## Инварианты

- каждая policy-required метрика присутствует в каждом acceptance-периоде;
- отсутствие обязательной метрики даёт `missing` и блокирует run;
- input не может понизить `required=true` из policy через `required:false`;
- изменение `tolerance_mode`, `absolute_tolerance` или `relative_tolerance_percent` относительно policy требует непустой `override_reason`;
- JSON/Markdown report фиксирует required coverage и причины overrides;
- CI проверяет passing, failing, incomplete и invalid-override scenarios.

Exact PR head `7e88182533f7d3a8baf813bcaeeb19d7442db0d3` прошёл Release integrity: version, acceptance-tools, Docker/gateway и backup/restore. P35 не затрагивал backend runtime, frontend runtime, зависимости, миграции или product VERSION, поэтому соответствующие path-filter workflows не запускались.

P35 не меняет runtime приложения и не повышает product version: baseline остаётся `0.9.0-alpha.11`.

Связанные документы: `DATA_ACCURACY_ACCEPTANCE.md`, `RELEASE_READINESS.md`, `RELEASE_ROADMAP.md`.
