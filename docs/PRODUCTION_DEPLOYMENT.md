# WB Insight — Production Deployment Baseline

Version line: `0.9.0-alpha.N`.

P25 establishes a reproducible container deployment baseline. It is intentionally infrastructure-neutral at the TLS/DNS layer: the stack exposes one HTTP entrypoint and expects the hosting platform/reverse proxy/load balancer to terminate HTTPS.

## Services

`compose.production.yml` starts:

- PostgreSQL 16;
- Redis 7 with AOF;
- one-shot Alembic migration service;
- FastAPI backend;
- Celery worker;
- Celery beat scheduler;
- compiled Vue frontend served by nginx;
- nginx same-origin proxy for API routes.

For a larger production installation PostgreSQL and Redis may be replaced by managed services. In that case keep the same environment contract and remove/override the bundled services.

## Required host preparation

1. Install a current Docker Engine with Compose v2.
2. Copy `.env.production.example` to `.env.production` outside source control.
3. Replace every placeholder secret/value.
4. Configure DNS and an HTTPS reverse proxy/load balancer in front of `${PUBLIC_HTTP_PORT}`.
5. Ensure only the public frontend port is internet-exposed; PostgreSQL, Redis and backend should remain private to the Docker network.

Production startup is fail-closed when mandatory security/WB configuration is absent.

## Deploy

```bash
cp .env.production.example .env.production
# edit .env.production

docker compose --env-file .env.production -f compose.production.yml build
docker compose --env-file .env.production -f compose.production.yml up -d
```

The `migrate` service runs `alembic upgrade head` before backend/worker startup. A failed migration prevents the application services from starting.

## Verification

```bash
docker compose --env-file .env.production -f compose.production.yml ps
curl -fsS http://127.0.0.1:${PUBLIC_HTTP_PORT:-8080}/health/live
curl -fsS http://127.0.0.1:${PUBLIC_HTTP_PORT:-8080}/health/ready
```

`/health/live` verifies the API process. `/health/ready` verifies PostgreSQL and Redis readiness.

Before public release, perform the end-to-end smoke from `docs/RELEASE_READINESS.md` through the public HTTPS hostname, not only localhost.

## Upgrade procedure

1. Snapshot/backup PostgreSQL according to the P26 backup policy.
2. Pull/checkout the exact release tag or commit.
3. Verify `VERSION` and `CHANGELOG.md`.
4. Build images.
5. Run the stack; migrations execute before application services.
6. Verify health endpoints and key smoke flows.
7. Keep the previous image/commit available until validation is complete.

## Rollback

Application rollback is performed by deploying the previous known-good release commit/tag. Database rollback is **not automatic**: Alembic downgrades can be destructive and must be evaluated migration-by-migration. If a release includes a non-backward-compatible migration, create and test a database restore point before deployment.

A formal backup/restore drill and RPO/RTO policy remain P26 blockers.

## Secrets

Never commit `.env.production`. The root `.gitignore` blocks `.env` and `.env.*` while explicitly allowing only `.env.production.example`.

At minimum, treat these as secrets:

- `DB_PASSWORD`;
- `API_TOKEN_ENCRYPTION_KEY`;
- `JWT_SECRET_KEY`;
- `WB_SERVICE_SECRET`;
- `SBER_USERNAME` / `SBER_PASSWORD`.

Prefer platform secret injection over a host file when supported. No real secret is copied into either Docker image.

## HTTPS boundary

The bundled nginx listens on container port 8080 and is not a TLS terminator. Production must place a TLS-enabled reverse proxy/load balancer in front of it and set:

- `SERVER_HTTP_PROTOCOL=https://`;
- correct `SERVER_ADDR`;
- `COOKIE_SECURE=true`;
- `ALLOWED_ORIGINS` to the real HTTPS origin;
- Sber return/fail URLs to the real HTTPS hostname.

## Current limitations

P25 does not claim the product is beta-ready. Remaining release blockers include monitoring/alerts, backup/restore drill, legal/consent persistence, browser access-token hardening, external WB/Sber credentials and full production smoke. See `docs/RELEASE_READINESS.md`.
