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
- Network: attach Lambda to the private subnets that can reach the PostgreSQL EC2 security group

## GitHub environment configuration

Create a GitHub environment named `production` and configure:

### Secret

- `AWS_LAMBDA_DEPLOY_ROLE_ARN`: IAM role assumed by GitHub Actions through OIDC

### Variables

- `AWS_REGION`: for example `ap-southeast-1`
- `AWS_LAMBDA_FUNCTION_NAME`: the deployed Lambda function name

The workflow intentionally does not run Alembic. Run migrations from the EC2 administrative host before deploying application code that requires a new schema.

## Dependency separation

- `requirements-api.txt`: dependencies packaged into Lambda
- `requirements-worker.txt`: Alembic, Excel import, tests, local Uvicorn, and administrative tooling

The workflow enforces a 200 MB uncompressed safety limit, below Lambda's 250 MB extracted ZIP limit.
