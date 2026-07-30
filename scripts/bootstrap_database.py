"""Create the recovered schema in a new, empty database."""

from app.core.database import engine
from app.models import Base


def main() -> None:
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    main()
