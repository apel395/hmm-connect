from sqlalchemy import func

from app.models.product import Product


def generate_item_code(
    db,
    group_code: str,
) -> str:
    prefix = f"{group_code}-"

    last_code = (
        db.query(Product.code)
        .filter(
            Product.code.like(f"{prefix}%")
        )
        .order_by(
            func.length(Product.code).desc(),
            Product.code.desc(),
        )
        .first()
    )

    if not last_code:
        return f"{group_code}-100001"

    current_code = last_code[0]

    current_number = int(
        current_code.split("-")[1]
    )

    next_number = current_number + 1

    return f"{group_code}-{next_number}"
