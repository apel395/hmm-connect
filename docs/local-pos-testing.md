# Local POS test environment (Windows / PowerShell)

This setup runs the POS feature branches using **a new database**, not MMH production. Do not use production `.env` files, database credentials, or backups.

## Prerequisites

- Docker Desktop with Linux containers and the Compose plugin
- Git
- Node.js 22 LTS and npm

Run these commands in **PowerShell** from a new folder (e.g. `C:\dev\hmm-pos-test`):

```powershell
git clone --branch feature/pos-customer-draft-repair-1023 https://github.com/apel395/hmm-connect.git hmm-connect-ui
git clone --branch feature/pos-customer-draft-repair-1023-backend https://github.com/apel395/hmm-connect.git hmm-connect-backend

cd .\hmm-connect-backend
docker compose -f docker-compose.pos-local.yml up -d --build
docker compose -f docker-compose.pos-local.yml exec api python scripts/bootstrap_database.py --confirm-empty-database
docker compose -f docker-compose.pos-local.yml exec api python scripts/seed_local_pos_test.py
```

Choose a password (at least eight characters) when prompted for the `postest` account. This bootstrap step is **only for the first run against an empty database**; skip it when restarting an existing local setup.

In a **second PowerShell terminal**, from the same parent directory:

```powershell
cd .\hmm-connect-ui
'VITE_API_URL=http://localhost:8000/api/v1' | Set-Content .env.local
npm ci
npm run dev
```

## URLs

- Frontend: <http://localhost:5173>
- Backend health: <http://localhost:8000/health>
- Backend Swagger: <http://localhost:8000/docs>
- Login: `postest` and the local password chosen during seeding

Go to `/pos` and choose **Invoice · AR**. Add a sample menu, use or create a customer, enter a due date, and **Save Draft**. Then open `/pos/sales` and use **Edit** to change quantity/price; save without changing the invoice number. Test **Post** after that. `Repair AR` appears only for legacy posted invoices with no AR record, not for new invoices.

## Isolation and daily operation

The Docker Compose setup binds to localhost ports `8000` and `55432`. Its database is named `hmm_pos_test`, with a separate volume `hmm_pos_test_data`. The local seed script refuses to run against any other database name. The API source is mounted for hot reload. The frontend runs in Vite dev mode.

```powershell
# Backend start/stop (from hmm-connect-backend)
docker compose -f docker-compose.pos-local.yml up -d
docker compose -f docker-compose.pos-local.yml down
docker compose -f docker-compose.pos-local.yml logs --tail=100 api
```

Do **not** run `docker compose down -v` unless you explicitly want to delete the local test database. Do not run bootstrap a second time; it intentionally refuses any database with tables. To run backend regression tests without affecting the local database, use the repository's `pytest` suite with its isolated fixtures.

If you see no products, confirm you chose **POS Test Pekanbaru** or no location filter. If login gives a session conflict, select **Sign in and end previous session**. If browser requests go to an old tunnel domain, confirm the UI file `.env.local` contains `VITE_API_URL=http://localhost:8000/api/v1` and restart `npm run dev`.
