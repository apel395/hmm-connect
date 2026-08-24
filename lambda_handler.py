"""AWS Lambda entry point for the HMM Connect FastAPI application."""

from mangum import Mangum

from app.main import app

# Lifespan is disabled because application startup/shutdown work should not run
# for every Lambda execution environment unless explicitly required later.
handler = Mangum(app, lifespan="off")
# Deployment marker: scoped posting rules schema is ready.
