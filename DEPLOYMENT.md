# HMM Connect production deployment

This runbook targets one Linux VPS with Docker Compose. PostgreSQL and the API are private to the Docker network. Only the web container is bound to localhost; terminate HTTPS with Caddy/Nginx or expose it through Cloudflare Tunnel.

## 1. Server prerequisites

- Linux VPS (2 vCPU / 4 GB RAM recommended starting point)
- Docker Engine + Docker Compose plugin
- Git
- A domain/subdomain for production
- Daily off-server PostgreSQL backup destination

## 2. Checkout

```bash
git clone git@github.com:apel395/hmm-connect.git
cd hmm-connect
git checkout testing/purchasing-ppn-e2e
```

For the final release, deploy the promoted release branch/tag rather than the testing branch.

## 3. Environment

```bash
cp .env.production.example .env.production
chmod 600 .env.production
```

Generate secrets rather than using the examples:

```bash
openssl rand -hex 32
openssl rand -base64 36
```

Set `POSTGRES_PASSWORD`, `SECRET_KEY`, and the final HTTPS origin in `CORS_ORIGINS`.

Do not commit `.env.production`.

## 4. Build

```bash
docker compose --env-file .env.production -f docker-compose.production.yml build
```

## 5. Database

This recovered repository has a legacy schema anchor. Do not assume `alembic upgrade head` is a valid empty-database bootstrap path.

For a new empty production database, use the repository's tested bootstrap workflow first, then validate the migration chain. For an existing database, take a backup and inspect the current Alembic revision before applying upgrades.

At minimum before changing an existing database:

```bash
docker compose --env-file .env.production -f docker-compose.production.yml up -d db
# create an off-server backup here
# inspect current revision and run the repository migration validator
```

Never experiment with migrations against the only copy of production data.

## 6. Start

```bash
docker compose --env-file .env.production -f docker-compose.production.yml up -d
```

Check:

```bash
docker compose --env-file .env.production -f docker-compose.production.yml ps
curl -fsS http://127.0.0.1:8080/healthz
curl -fsS http://127.0.0.1:8080/api/v1/health || true
```

The backend also exposes `/health` internally. The frontend uses `/api/v1` on the same origin, so production does not depend on a temporary `trycloudflare.com` API URL.

## 7. HTTPS

Recommended topology:

```text
Internet
  -> HTTPS reverse proxy / Cloudflare Tunnel
  -> 127.0.0.1:8080 (web)
  -> /api/* -> api:8080
  -> PostgreSQL (Docker internal only)
```

Do not publish PostgreSQL port 5432 to the Internet.

## 8. Backups

Back up at least:

- PostgreSQL database daily
- `document_uploads` volume
- production environment/secrets in a secure password manager

Keep at least one backup outside the VPS and periodically test restore.

## 9. Update procedure

```bash
git fetch --all --prune
git checkout <release-branch-or-tag>
git pull --ff-only
docker compose --env-file .env.production -f docker-compose.production.yml build
# backup DB before migrations
docker compose --env-file .env.production -f docker-compose.production.yml up -d
```

After deployment, smoke-test login and the critical PR -> PO -> RR -> Inventory -> Supplier Invoice -> AP -> Payment flow.

## 10. Rollback

Application rollback: checkout the previous release tag/commit and rebuild containers.

Database rollback: restore the pre-deployment backup when a migration changed persisted data. Do not rely on Alembic downgrade as the only production rollback plan.
