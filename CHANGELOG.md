# Changelog

All notable product milestones are documented here. Versions before the introduction of the release policy on 2026-09-15 are reconstructed from the complete `main` history and merged pull requests; they describe product maturity and do not imply that a Git tag existed at that date.

## [0.9.0-alpha.2] — 2026-09-15

Release-governance and P25 production-deployment baseline.

- established root `VERSION` as canonical product version;
- aligned backend/frontend version metadata;
- documented SemVer, `alpha -> beta -> rc -> stable` transition rules;
- added detailed reconstructed release history;
- started reproducible production container/deployment baseline.

## [0.9.0-alpha.1] — 2026-09-15

Release-hardening baseline after P19–P24.

### P19 — Wildberries credential compliance — PR #34

- WB token type is derived from JWT claim `acc`, not frontend input;
- real `exp` is used instead of an artificial 180-day lifetime;
- Personal/Test tokens are rejected for the cloud flow;
- Service token is bound to configured service identity;
- WB auth header moved to documented Bearer form.

### P20 — Marketplace adapter core — PR #35

- introduced generic `MarketplaceAdapter` contract and registry;
- moved WB handlers behind `WildberriesAdapter`;
- generic sync orchestration became marketplace-aware without duplicating worker infrastructure.

### P21 — Marketplace credential foundation — PR #36

- credentials gained `external_account_id`;
- expiration became nullable for non-expiring marketplace keys;
- WB seller identity is preserved separately from encrypted secret material;
- legacy credential endpoint regressions were corrected.

### P22 — WB access-token policy and live validation — PR #37

- required WB API categories and read-only permission mask are validated;
- production requires partner `WB_SERVICE_ID` and `WB_SERVICE_SECRET`;
- Base/Service seller requests use partner `X-Client-Secret`;
- token is live-validated against WB before persistence;
- revoked/invalid credentials fail closed.

### P23 — Release readiness baseline — PR #38

- added liveness/readiness endpoints;
- readiness checks PostgreSQL and Redis;
- README/SETUP were aligned with the actual product state;
- explicit release blockers and Definition of Done were recorded.

### P24 — Production Sber acquiring flow — PR #39

- server-to-server payment registration and status verification;
- idempotent payment attempts;
- callback treated only as a trigger, never as proof of payment;
- subscription activates only after bank-confirmed deposited state;
- payment event log, duplicate-activation protection and sandbox/production separation.

## [0.8.0-alpha.1] — 2026-09-15

Feature-complete WB analytics alpha after P14–P18.

### P14 — Dashboard UX foundation — PR #29

- unified calm application design system;
- restructured Overview / Unit Economy / Ads UX;
- removed demo/hardcoded KPI values;
- corrected period/filter propagation and metric labels.

### P15 — Seller inputs and settings workspace — PR #30

- real seller profile editing;
- WB account workspace;
- cost-price input with effective dates and CSV path;
- manual expense management;
- settings UI aligned with the main design system.

### P16 — Inventory risk and replenishment planning — PR #31

- 30-completed-day demand model;
- stock-cover calculation;
- critical stock threshold and replenishment recommendation;
- dedicated stocks dashboard with account scope.

### P17 — Price monitoring and history — PR #32

- durable WB price snapshot sync;
- change-only price history;
- size-aware current price model;
- prices dashboard and account filtering.

### P18 — Finance reports and payout reconciliation — PR #33

- canonical WB finance report summaries;
- current balance snapshot;
- report summary/detail reconciliation with tolerance;
- finance dashboard and durable finance sync.

## [0.7.0-alpha.1] — 2026-09-15

Semantic/data-model maturation after P8–P13.

### P8 — Unified semantic metrics — PR #23

- shared semantic metrics layer;
- operational orders separated from finance realization facts;
- advertising attribution separated from total orders;
- corrected comparison periods, Moscow-day boundaries and sync status semantics.

### P9 — Multi-account dashboard filter — PR #24

- unified `DashboardAccountScope`;
- safe selected-account and all-allowed-accounts modes;
- SQL-level scoping across Main, Charts, Ads and Unit Economy;
- frontend account selector persisted across analytics sections.

### P10 — Unit Economy correctness — PR #25

- repaired obsolete aliases/runtime mismatches;
- aggregate ratios recalculated from numerators/denominators;
- actual advertising spend included by SKU;
- API contract aligned with frontend expectations.

### P11 — Monthly revenue plans — PR #26

- persistent monthly revenue targets per WB account;
- correct calendar month length;
- separate required revenue/day and orders/day metrics;
- all-accounts plan aggregation without invented fallback targets.

### P12 — Durable paid storage sync — PR #27

- official WB Paid Storage task/status/download flow;
- durable task checkpoints and <=8-day chunks;
- rolling refresh and idempotent replacement semantics.

### P13 — Historical COGS and seller expenses — PR #28

- date-effective cost-price history;
- account/SKU manual expenses;
- Unit Economy and Main profit use historical COGS and scoped expenses;
- cost-price API was properly registered.

## [0.6.0-alpha.1] — 2026-09-14

Operational WB data foundation after P5–P7.

### P5 — Orders and sales facts — PR #20

- account-scoped WB orders and sales/returns facts;
- canonical identities and stale-update protection;
- durable source cursors and retention-aware initial sync.

### P6 — Advertising sync — PR #21

- current Promotion API campaign discovery and fullstats v3 ingestion;
- account-scoped ad facts and rolling refresh;
- campaign batching, typed permission errors and durable checkpoints.

### P7 — Daily sales funnel — PR #22

- product funnel facts by account/product/day;
- views, carts, orders, buyouts and conversion metrics;
- 20-item batching, 7-day refresh and durable checkpointing;
- typed handling of feature-unavailable responses.

## [0.5.0-alpha.1] — 2026-09-14

Production-safety and durable-sync foundation after P0–P4.

### P0 — Production safety — PR #15

- strict access/refresh JWT separation and safer refresh/logout flow;
- server-side RBAC for control panel;
- protected user/role administration;
- marketplace credential secrecy and tariff account limits;
- fail-closed billing defaults;
- audit logging and migration/test CI baseline.

### P1 — Account-scoped sync — PR #16

- sync state/job identity moved to exact marketplace credential;
- scheduler and worker enforce ownership, validity and tariff allowance;
- migrations made reproducible and checked against clean PostgreSQL.

### P2 — WB transport hardening — PR #17

- Redis-coordinated endpoint/account rate limiting;
- bounded retries, `Retry-After`, typed transport/auth/rate errors;
- credential deactivation only on confirmed auth failures;
- deterministic resource cleanup.

### P3 — WB API contracts and pagination — PR #18

- current Finance, Stocks and Content request/response contracts;
- safe pagination and cursor-stall protection;
- account-scoped finance/product/stock identities;
- normalized current API payloads.

### P4 — Durable resumable jobs — PR #19

- atomic job claims with leases;
- crash recovery and bounded retries;
- committed page checkpoints for Finance/Stocks/Products;
- restart resumes from last persisted page rather than the beginning.

## [0.4.0-alpha.1] — 2026-05-07

Database/documentation consolidation milestone.

- merged PR #14 with database requirements/notes updates;
- consolidated early persistence assumptions before the September production audit.

## [0.3.0-alpha.1] — 2026-05-06

Early Wildberries synchronization and advertising milestone.

- PR #8: corrected sync behavior around invalid marketplace tokens;
- PR #9: advertising statistics synchronization;
- PR #10 and #11: advertising page/backend/frontend iteration;
- PR #12: advertising import correction.

PR #13 was closed without merge and is not part of the mainline release history.

## [0.2.0-alpha.1] — 2026-05-05

Initial Unit Economy milestone.

- PRs #4–#7 progressively introduced and refined the first WB reports / unit-economy implementation.

## [0.1.0-alpha.1] — 2026-03-30

Repository reconstruction baseline.

- PR #1 established the first reconstructed codebase on `main`.
- PRs #2 and #3 were closed without merge and therefore are excluded from product versions.

## Versioning interpretation

The project remained in `0.x` because no public stable contract had yet been declared. The September P0–P24 work substantially changed authentication, data identities, API contracts, sync semantics, finance logic and release infrastructure; calling any of those states `1.0.0` would have falsely signaled stability.

The target sequence for WB Web v1 is now:

`0.9.0-alpha.N` -> `0.9.0-beta.N` -> `1.0.0-rc.N` -> `1.0.0`.
