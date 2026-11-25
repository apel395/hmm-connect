# AWS Lambda ZIP deployment

The normal FastAPI API is deployed as a ZIP package to AWS Lambda. Database migrations, historical imports, and other administrative jobs remain outside the request path and use `requirements-worker.txt` on the EC2 administration/database host.

## Lambda configuration

- Runtime: Python 3.13
- Architecture: x86_64
- Handler: `lambda_handler.handler`
- Memory: 1024 MB initially
- Timeout: 30 seconds initially
- Reserved concurrency: 10 initially
- Environment variables: use the same names consumed by `app.core.config`
- Network: attach Lambda to the VPC subnets that can reach both the primary and demo PostgreSQL databases on EC2

## Demo database routing

The public URL does not change. Configure `DEMO_DATABASE_URL` with the separate demo DB URL and `DEMO_USERNAMES` with the exact demo username(s), for example `demo`. At `POST /api/v1/auth/login`, an exact allowlisted username authenticates against the demo DB and receives a signed `db=demo` claim. Every subsequent request uses that claim to select the database; all other accounts use the primary DB.

Never point `DEMO_DATABASE_URL` at `DATABASE_URL`. If a demo username is configured but its database URL is missing, demo login fails closed with HTTP 503 instead of falling back to production data.

Create or rotate the demo account only on EC2, after confirming the demo DB is migrated:

```bash
source .venv/bin/activate
export DEMO_DATABASE_URL='postgresql://.../erp_demo'
export DEMO_USERNAMES='demo'
export DEMO_PASSWORD='<strong-password>'
python -m scripts.seed_demo_account --username demo --confirm-demo-database
```

The script refuses a target database with the same name as the primary DB and clears any active demo session when rotating the password. Short demo-only passwords require the additional `--allow-weak-password` flag; never apply that flag to primary accounts.

## GitHub environment configuration

Create a GitHub environment named `production` and configure:

### Secret

- `AWS_LAMBDA_DEPLOY_ROLE_ARN`: IAM role assumed by GitHub Actions through OIDC

### Variables

- `AWS_REGION`: for example `ap-southeast-1`
- `AWS_LAMBDA_FUNCTION_NAME`: the deployed Lambda function name
- `AWS_LAMBDA_FUNCTION_URL`: optional Function URL used by the post-deployment `/health` smoke test

The workflow intentionally does not run Alembic. Run migrations from the EC2 administrative host before deploying application code that requires a new schema.

## Fresh database bootstrap

The recovered historical migration chain assumes that legacy base tables already exist. Do not run the historical chain against a brand-new empty database.

For the first initialization of a new empty database, run from the repository root on the EC2 administration host:

```bash
source .venv/bin/activate
python -m scripts.bootstrap_database --confirm-empty-database
```

The command refuses to run when any public table already exists. It creates the current schema from SQLAlchemy metadata, validates core tables, and stamps the database at the current Alembic head.

After this one-time bootstrap, every later schema change must use normal Alembic migrations:

```bash
alembic upgrade head
```

Do not run the bootstrap command again after application data exists.

Database passwords may contain URL-encoded characters such as `%40`. `alembic/env.py` escapes percent signs only when passing the URL through Alembic's ConfigParser; the value in `.env` remains normally URL-encoded.

## Dependency separation

- `requirements-api.txt`: dependencies packaged into Lambda
- `requirements-worker.txt`: Alembic, Excel import, tests, local Uvicorn, and administrative tooling

The workflow enforces a 200 MB uncompressed safety limit, below Lambda's 250 MB extracted ZIP limit.
