"""replace supplier master data

Revision ID: 20260717_suppliers
Revises: 9c3f6a1b2d4e
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260717_suppliers"
down_revision: Union[str, Sequence[str], None] = "9c3f6a1b2d4e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SUPPLIERS = [
    {
        "code": "SUP-001",
        "name": "CV. AMANAH TRIUTAMA",
        "location": None,
        "pic_name": "Pak Capa",
        "address": "Jl. Siaga Dalam No 209 RT 17, Balikpapan kota",
        "bank_name": "Mandiri",
        "bank_account_number": "1490004796308",
        "bank_account_name": "Safaruddin Asri",
        "items": "Vegetable dan Fruit",
    },
    {
        "code": "SUP-002",
        "name": "PT. LISTY HARJO MAKMUR",
        "location": None,
        "pic_name": "Bu Ima",
        "address": "Jl. Bukit Cinta RT 28 No 73 Kel Damai Kec Balikpapan, Kota Balikpapan",
        "bank_name": "Mandiri",
        "bank_account_number": "1420033322255",
        "bank_account_name": "PT. LISTY HARJO MAKMUR",
        "items": "Dry, Monouse, Beverage dan Frozen (Ayam, Daging, Ikan)",
    },
    {
        "code": "SUP-003",
        "name": "TPS Club",
        "location": "PHM",
        "pic_name": "Pak Ipan",
        "address": "Jl. Projakal Kelurahan Batu Ampat Kecamatan Balikpapan Utara, Kode pos 76127",
        "bank_name": "BCA",
        "bank_account_number": "3193077109",
        "bank_account_name": "PT. INDOMARCO ADI PRIMA",
        "items": "Air Gallon",
    },
    {
        "code": "SUP-004",
        "name": "PT Rentokil Indonesia",
        "location": None,
        "pic_name": "Pak Fajar",
        "address": "Jl. MT Haryono RT 43 No 6A Kel Graha Indah Kec Balikpapan Utara, Balikpapan",
        "bank_name": "Mandiri",
        "bank_account_number": "88611700065045",
        "bank_account_name": "PT. Rentokil Indonesia",
        "items": "Hama",
    },
    {
        "code": "SUP-005",
        "name": "CV Ria",
        "location": None,
        "pic_name": "Pak Androw",
        "address": "Jl Pandan Sari No 80 RT 022, Kec. Balikpapan Barat, Kel. Marga sari, Balikpapan 76131",
        "bank_name": "Mandiri",
        "bank_account_number": "1490016652820",
        "bank_account_name": "CV Ria",
        "items": "Meal Box",
    },
    {
        "code": "SUP-006",
        "name": "Supri",
        "location": None,
        "pic_name": "Pak Supri",
        "address": "Jl. Yos Sudarso RT 10 Sarijaya, Sangasanga",
        "bank_name": "BNI",
        "bank_account_number": "0394308957",
        "bank_account_name": "Slamet Supriyanto",
        "items": "Frozen (Ayam, Daging, Ikan)",
    },
    {
        "code": "SUP-007",
        "name": "Pak Puguh",
        "location": None,
        "pic_name": "Puguh",
        "address": "Jl. Slamet Riadi No.3, Bantuas, Kec Sangasanga, Kab. Kutai Kartanegara, Kalimantan Timur",
        "bank_name": "BNI",
        "bank_account_number": "1719269958",
        "bank_account_name": "Puguh Wibowo",
        "items": "Ayam, Vegetable, Fruit",
    },
    {
        "code": "SUP-008",
        "name": "Kafka",
        "location": "PEP",
        "pic_name": "Pak Warno",
        "address": "Jalan Mada Sanga Sanga Dalam, Sanga Sanga Dalam, Sanga-Sanga (Atm bni atm bri), KAB. KUTAI KARTANEGARA, SANGA-SANGA, KALIMANTAN TIMUR, ID, 75254",
        "bank_name": "Mandiri",
        "bank_account_number": "1480012294677",
        "bank_account_name": "Suwarno",
        "items": "Dry, Monouse, Beverage",
    },
    {
        "code": "SUP-009",
        "name": "Hikmah",
        "location": None,
        "pic_name": "Bu Hikmah",
        "address": "Jalan Provinsi RT 04 Pasar Subuh Makroman, Kota samarinda, Provinsi kalimantan timur",
        "bank_name": "BNI",
        "bank_account_number": "1173677330",
        "bank_account_name": "Hikmah",
        "items": "All In",
    },
    {
        "code": "SUP-010",
        "name": "Bu Erni / Ace Mart",
        "location": None,
        "pic_name": "Bu Erny",
        "address": "Jl. Merbabu No 27, Samarinda",
        "bank_name": "BCA",
        "bank_account_number": "0278002899",
        "bank_account_name": "ERNY SULISTIO",
        "items": "Air Gallon",
    },
    {
        "code": "SUP-011",
        "name": "Bu Ana / Rumah Makan Sederhana",
        "location": None,
        "pic_name": "Bu Ana",
        "address": "Danau Samboja RT 06 Kelurahan Sungai Seluang Kec Samboja",
        "bank_name": "BRI",
        "bank_account_number": "447801016862538",
        "bank_account_name": "Rusdiana",
        "items": "Rumah Makan",
    },
    {
        "code": "SUP-012",
        "name": "Batam Provison Services",
        "location": None,
        "pic_name": "Pak Yanto",
        "address": "Pasar Puja Bahari Kios Blok B 13-15 Lubuk Baja, Kota Batam",
        "bank_name": "MANDIRI",
        "bank_account_number": "1090015566557",
        "bank_account_name": "CV BATAM PROVISION SERVICES",
        "items": "Dry, Vegetable, Fruit",
    },
    {
        "code": "SUP-013",
        "name": "PT Kharisma Karya Kartika",
        "location": "BATAM",
        "pic_name": "Bu Dewi",
        "address": "Jl Budi kemuliaan, Blok ph no 90, Kampung seraya - Batam",
        "bank_name": "BCA",
        "bank_account_number": "617181111",
        "bank_account_name": "PT Kharisma Karya Kartika",
        "items": "Frozen (Ayam, Daging, Ikan)",
    },
    {
        "code": "SUP-014",
        "name": "Rezekindo Makmur Sentosa",
        "location": "BATAM",
        "pic_name": "Ko Akeng",
        "address": "Komp. Nagoya Newton, Blok E, No 1 dan 2 RT 01 RW 08 Lubuk Baja Kota, Kec. Lubuk Baja, Kota Batam",
        "bank_name": "BCA",
        "bank_account_number": "8520491199",
        "bank_account_name": "Rezekindo Makmur Sentosa",
        "items": "Fruit",
    },
]


supplier_table = sa.table(
    "suppliers",
    sa.column("code", sa.String()),
    sa.column("name", sa.String()),
    sa.column("location", sa.String()),
    sa.column("pic_name", sa.String()),
    sa.column("address", sa.Text()),
    sa.column("bank_name", sa.String()),
    sa.column("bank_account_number", sa.String()),
    sa.column("bank_account_name", sa.String()),
    sa.column("items", sa.Text()),
    sa.column("is_active", sa.Boolean()),
)


def upgrade() -> None:
    op.add_column(
        "suppliers",
        sa.Column("location", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "suppliers",
        sa.Column("pic_name", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "suppliers",
        sa.Column("bank_name", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "suppliers",
        sa.Column("bank_account_number", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "suppliers",
        sa.Column("bank_account_name", sa.String(length=150), nullable=True),
    )
    op.add_column(
        "suppliers",
        sa.Column("items", sa.Text(), nullable=True),
    )

    op.execute(
        sa.text(
            "DELETE FROM purchase_order_items "
            "WHERE purchase_order_id IN "
            "(SELECT id FROM purchase_orders)"
        )
    )
    op.execute(sa.text("DELETE FROM purchase_orders"))
    op.execute(sa.text("DELETE FROM suppliers"))

    op.bulk_insert(
        supplier_table,
        [
            {
                **supplier,
                "is_active": True,
            }
            for supplier in SUPPLIERS
        ],
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM suppliers"))

    op.drop_column("suppliers", "items")
    op.drop_column("suppliers", "bank_account_name")
    op.drop_column("suppliers", "bank_account_number")
    op.drop_column("suppliers", "bank_name")
    op.drop_column("suppliers", "pic_name")
    op.drop_column("suppliers", "location")
