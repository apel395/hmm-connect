"""seed item classification

Revision ID: 9c3f6a1b2d4e
Revises: 81bae4fc56c1
Create Date: 2026-07-17 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9c3f6a1b2d4e"

down_revision: Union[
    str,
    Sequence[str],
    None,
] = "81bae4fc56c1"

branch_labels: Union[
    str,
    Sequence[str],
    None,
] = None

depends_on: Union[
    str,
    Sequence[str],
    None,
] = None


GROUPS = [
    ("1", "FOOD"),
    ("2", "BEVERAGE"),
    ("3", "MATERIAL"),
    ("4", "ASSET"),
]


SUBGROUPS = [
    ("1-1", "MEAT", "1"),
    ("1-2", "POULTRY", "1"),
    ("1-3", "FISH", "1"),
    ("1-4", "VEGETABLE", "1"),
    ("1-5", "FRUIT", "1"),
    ("2-1", "MINERAL WATER", "2"),
    ("2-2", "SOFT DRINK", "2"),
    ("2-3", "COFFEE", "2"),
    ("2-4", "TEA", "2"),
    ("3-1", "GUEST SUPPLIES", "3"),
    ("3-2", "HOUSEKEEPING", "3"),
    ("3-3", "OFFICE SUPPLIES", "3"),
    ("4-1", "BUILDING", "4"),
    ("4-2", "EQUIPMENT", "4"),
    ("4-3", "FURNITURE", "4"),
]


def upgrade() -> None:
    connection = op.get_bind()

    connection.execute(
        sa.text(
            """
            UPDATE item_groups
            SET is_active = FALSE
            WHERE code = '0'
            """
        )
    )

    connection.execute(
        sa.text(
            """
            UPDATE item_subgroups
            SET is_active = FALSE
            WHERE code = '0-0'
            """
        )
    )

    for code, name in GROUPS:
        connection.execute(
            sa.text(
                """
                INSERT INTO item_groups (
                    code,
                    name,
                    is_active
                )
                VALUES (
                    :code,
                    :name,
                    TRUE
                )
                ON CONFLICT (code)
                DO UPDATE SET
                    name = EXCLUDED.name,
                    is_active = TRUE
                """
            ),
            {
                "code": code,
                "name": name,
            },
        )

    for code, name, group_code in SUBGROUPS:
        connection.execute(
            sa.text(
                """
                INSERT INTO item_subgroups (
                    code,
                    name,
                    group_id,
                    is_active
                )
                SELECT
                    :subgroup_code,
                    :subgroup_name,
                    id,
                    TRUE
                FROM item_groups
                WHERE code = :group_code
                ON CONFLICT (code)
                DO UPDATE SET
                    name = EXCLUDED.name,
                    group_id = EXCLUDED.group_id,
                    is_active = TRUE
                """
            ),
            {
                "subgroup_code": code,
                "subgroup_name": name,
                "group_code": group_code,
            },
        )


def downgrade() -> None:
    connection = op.get_bind()

    connection.execute(
        sa.text(
            """
            UPDATE item_subgroups
            SET is_active = FALSE
            WHERE code IN (
                '1-1', '1-2', '1-3', '1-4', '1-5',
                '2-1', '2-2', '2-3', '2-4',
                '3-1', '3-2', '3-3',
                '4-1', '4-2', '4-3'
            )
            """
        )
    )

    connection.execute(
        sa.text(
            """
            UPDATE item_groups
            SET is_active = FALSE
            WHERE code IN ('1', '2', '3', '4')
            """
        )
    )

    connection.execute(
        sa.text(
            """
            UPDATE item_groups
            SET is_active = TRUE
            WHERE code = '0'
            """
        )
    )

    connection.execute(
        sa.text(
            """
            UPDATE item_subgroups
            SET is_active = TRUE
            WHERE code = '0-0'
            """
        )
    )
