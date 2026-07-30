from sqlalchemy import ForeignKey, Numeric

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.models.base import Base


class JournalVoucherLine(Base):

    __tablename__ = "journal_voucher_lines"

    id: Mapped[int] = mapped_column(primary_key=True)

    voucher_id: Mapped[int] = mapped_column(
        ForeignKey("journal_vouchers.id")
    )

    account_id: Mapped[int] = mapped_column(
        ForeignKey("chart_of_accounts.id")
    )

    debit: Mapped[float] = mapped_column(
        Numeric(18, 2),
        default=0,
    )

    credit: Mapped[float] = mapped_column(
        Numeric(18, 2),
        default=0,
    )

    description: Mapped[str | None]

    account = relationship(
        "ChartOfAccount"
    )
