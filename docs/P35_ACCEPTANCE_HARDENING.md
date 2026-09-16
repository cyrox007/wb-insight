# P35 — hardening обязательного data-accuracy coverage

P35 закрывает обход beta data-accuracy gate, при котором входной acceptance dataset мог не включать policy-required метрики или расширять tolerance без фиксированной причины.

## Инварианты

- каждая policy-required метрика присутствует в каждом acceptance-периоде;
- отсутствие обязательной метрики даёт `missing` и блокирует run;
- input не может понизить `required=true` из policy через `required:false`;
- изменение `tolerance_mode`, `absolute_tolerance` или `relative_tolerance_percent` относительно policy требует непустой `override_reason`;
- JSON/Markdown report фиксирует required coverage и причины overrides;
- CI проверяет passing, failing, incomplete и invalid-override scenarios.

P35 не меняет runtime приложения и не повышает product version: baseline остаётся `0.9.0-alpha.11`.

Связанные документы: `DATA_ACCURACY_ACCEPTANCE.md`, `RELEASE_READINESS.md`, `RELEASE_ROADMAP.md`.
