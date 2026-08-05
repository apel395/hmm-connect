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
- Network: attach Lambda to the VPC subnets that can reach the PostgreSQL EC2 security group

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
