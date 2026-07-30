from sqlalchemy.orm import Session

from app.seeds.chart_of_accounts import (
    seed_chart_of_accounts,
)


def seed_database(db: Session):

    seed_chart_of_accounts(db)
