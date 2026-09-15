# WB Insight — Versioning Policy

WB Insight follows Semantic Versioning in the form:

`MAJOR.MINOR.PATCH[-PRERELEASE]`

Examples:

- `0.9.0-alpha.3`
- `0.9.0-beta.1`
- `1.0.0-rc.1`
- `1.0.0`

## Meaning of the numbers

### MAJOR

Breaking product/API changes after the first stable release.

Before `1.0.0`, the project may still change contracts quickly, therefore all pre-release work stays in major version `0`.

### MINOR

A meaningful product milestone: a new finished functional area or a release-readiness stage. During the `0.x` cycle we increment MINOR when the product moves to a clearly new capability level.

### PATCH

Backward-compatible corrections inside an already released capability set. For pre-release builds, normal development iterations are primarily represented by the prerelease counter (`alpha.1`, `alpha.2`, etc.); PATCH is reserved for fixes to an already published milestone.

## Prerelease stages

### `alpha`

The product is still under active development. Core functionality may be broad, but release blockers, operational gaps, external credentials, deployment work, monitoring, legal flows or smoke tests may remain.

Alpha criteria:

- architecture and data model can still evolve;
- incomplete release infrastructure is acceptable;
- external integrations may require onboarding/credentials;
- migrations and API contracts can still change before beta.

### `beta`

Feature scope of the target release is frozen. No planned major user-facing functionality is missing for that release; work is focused on defects, UX polish, compatibility and production validation.

For WB Web v1, `0.9.0-beta.1` is allowed only when all code-side P0 release blockers are closed and a production-like environment can execute the end-to-end smoke flow.

### `rc`

Release Candidate. The exact build is a candidate for stable publication. Only release-blocking fixes are accepted; each such fix produces another RC (`rc.2`, `rc.3`, ...).

For WB Web v1, RC requires:

- production deployment reproducible from the repository;
- WB production credentials configured and smoke-tested;
- Sber production acquiring smoke-tested;
- monitoring/alerts enabled;
- backup and restore drill completed;
- legal/consent flows published;
- security/session hardening completed;
- full release smoke passed.

### stable

Stable versions have no prerelease suffix. The first public stable release is `1.0.0`.

## Current release line

`0.9.0-alpha.2` is the current version on `main` after P25.

P26 is the **`0.9.0-alpha.3` candidate**. It becomes the repository version only after its required CI checks pass and the P26 PR is merged into `main`.

The next intended transitions are:

1. `0.9.0-alpha.3` — P26 operations monitoring / backup hardening;
2. `0.9.0-alpha.4` — P27 legal / consent;
3. `0.9.0-alpha.5` — P28 browser-session hardening / release smoke;
4. `0.9.0-beta.1` — WB Web v1 feature freeze and production-like validation;
5. `1.0.0-rc.1` — production candidate with all external/ops blockers closed;
6. `1.0.0` — public stable WB Web v1.

A beta or RC number must never be assigned merely because many commits have accumulated. Stage changes are gated by `docs/RELEASE_READINESS.md`.

## Version source of truth

The root `VERSION` file is the canonical product version. Backend runtime reads that file and frontend `package.json` must match it in release PRs. Release PRs must also update `CHANGELOG.md`.

`package-lock.json` is dependency-resolution metadata and is not treated as a product-version source of truth.

## Git tags

Stable and externally distributed prereleases should be tagged with the exact version prefixed by `v`, for example:

- `v0.9.0-beta.1`
- `v1.0.0-rc.1`
- `v1.0.0`

Historical versions in `CHANGELOG.md` before this policy are reconstructed milestones, not claims that an immutable Git tag existed at that time.
