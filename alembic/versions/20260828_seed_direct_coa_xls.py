"""Seed direct COA mappings from the Finance COA workbook.

Revision ID: 20260828_seed_direct_coa_xls
Revises: 20260828_location_repair_v2

The workbook carries location-specific AP, inventory, AR, accrual and cash
accounts.  This migration stores those as direct accounting settings keyed by
location; it does not recreate Posting Rules and does not touch posted journals.
Only deterministic workbook name/location matches are seeded.
"""

from alembic import op


revision = "20260828_seed_direct_coa_xls"
down_revision = "20260828_location_repair_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # These are ACCOUNT rows in the approved COA workbook. Activate the mapped
    # leaves because DirectCoaService requires active posting accounts.
    op.execute(
        """
        UPDATE chart_of_accounts
        SET is_active = true,
            is_posting = true
        WHERE account_number IN (
            '100-500-100',
            '200-100-1','200-100-2','200-100-3','200-100-4','200-100-5',
            '200-100-6','200-100-7','200-100-8','200-100-9','200-100-10',
            '100-300-100','100-300-101','100-300-102','100-300-103','100-300-104',
            '100-300-105','100-300-106','100-300-107','100-300-108','100-300-109',
            '100-300-500','100-300-501','100-300-502','100-300-503','100-300-504',
            '100-300-505','100-300-506','100-300-507','100-300-508','100-300-509',
            '100-300-700','100-300-701','100-300-702','100-300-703','100-300-704',
            '100-300-705','100-300-706','100-300-707','100-300-708','100-300-709',
            '100-200-102','100-200-103','100-200-104','100-200-105','100-200-106',
            '100-200-107','100-200-108','100-200-109','100-200-110','100-200-111',
            '200-200-100','200-200-101','200-200-102','200-200-103','200-200-104',
            '200-200-105','200-200-106','200-200-107','200-200-108','200-200-109',
            '100-100-100','100-100-101','100-100-102','100-100-106','100-100-107',
            '100-100-108','100-100-109','100-100-110','100-100-111','100-100-112'
        )
        """
    )

    # Global Input VAT from the workbook.
    op.execute(
        """
        INSERT INTO accounting_settings (setting_key, account_id, description)
        SELECT
            'INPUT_VAT_ACCOUNT',
            coa.id,
            'Direct COA from Finance workbook: Pajak Ppn Masukan'
        FROM chart_of_accounts coa
        WHERE coa.account_number = '100-500-100'
          AND coa.is_active = true
          AND coa.is_posting = true
        ON CONFLICT (setting_key)
        DO UPDATE SET
            account_id = EXCLUDED.account_id,
            description = EXCLUDED.description
        """
    )

    # Location mappings.  Account numbers are taken directly from COA(1).xlsx.
    #
    # LOCATION_<id>_AP
    # LOCATION_<id>_INVENTORY_FOOD
    # LOCATION_<id>_INVENTORY_BEVERAGE
    # LOCATION_<id>_INVENTORY_MATERIAL
    # LOCATION_<id>_AR
    # LOCATION_<id>_ACCRUAL
    # LOCATION_<id>_PETTY_CASH
    op.execute(
        """
        WITH location_map(
            alias_rx,
            bu_rx,
            ap_no,
            food_no,
            beverage_no,
            material_no,
            ar_no,
            accrual_no,
            petty_no
        ) AS (
            VALUES
                ('.*',                 '^hotel$',       '200-100-1',  '100-300-100','100-300-500','100-300-700','100-200-102','200-200-100',NULL),
                ('(libo|petapahan)',   'catering',      '200-100-2',  '100-300-101','100-300-501','100-300-701','100-200-103','200-200-101','100-100-101'),
                ('(zamp|pedada)',      'catering',      '200-100-3',  '100-300-102','100-300-502','100-300-702','100-200-104','200-200-102','100-100-102'),
                ('(rumbai|minas)',     'catering',      '200-100-4',  '100-300-103','100-300-503','100-300-703','100-200-105','200-200-103','100-100-100'),
                ('balikpapan',         'catering',      '200-100-5',  '100-300-104','100-300-504','100-300-704','100-200-106','200-200-104','100-100-106'),
                ('sanga',              'catering',      '200-100-6',  '100-300-105','100-300-505','100-300-705','100-200-107','200-200-105','100-100-110'),
                ('(batam|dellmott)',   'catering',      '200-100-7',  '100-300-106','100-300-506','100-300-706','100-200-108','200-200-106','100-100-108'),
                ('duri',               'catering',      '200-100-8',  '100-300-107','100-300-507','100-300-707','100-200-109','200-200-107','100-100-109'),
                ('phkt',               'catering',      '200-100-9',  '100-300-108','100-300-508','100-300-708','100-200-110','200-200-108',NULL),
                ('prcc',               'catering',      '200-100-10', '100-300-109','100-300-509','100-300-709','100-200-111',NULL,NULL),
                ('head.*office',       'catering',      NULL,         NULL,NULL,NULL,NULL,'200-200-109','100-100-107'),
                ('rockhan',            NULL,            NULL,         NULL,NULL,NULL,NULL,NULL,'100-100-111'),
                ('hulu',               NULL,            NULL,         NULL,NULL,NULL,NULL,NULL,'100-100-112')
        ),
        resolved AS (
            SELECT
                l.id AS location_id,
                m.*
            FROM locations l
            LEFT JOIN business_units bu ON bu.id = l.business_unit_id
            JOIN location_map m
              ON (m.bu_rx IS NULL OR lower(COALESCE(bu.name, '')) ~ m.bu_rx)
             AND lower(COALESCE(l.name, '') || ' ' || COALESCE(l.code, '')) ~ m.alias_rx
            WHERE l.is_active = true
        ),
        pairs AS (
            SELECT
                r.location_id,
                x.role,
                x.account_number
            FROM resolved r
            CROSS JOIN LATERAL (
                VALUES
                    ('AP', r.ap_no),
                    ('INVENTORY_FOOD', r.food_no),
                    ('INVENTORY_BEVERAGE', r.beverage_no),
                    ('INVENTORY_MATERIAL', r.material_no),
                    ('AR', r.ar_no),
                    ('ACCRUAL', r.accrual_no),
                    ('PETTY_CASH', r.petty_no)
            ) AS x(role, account_number)
            WHERE x.account_number IS NOT NULL
        )
        INSERT INTO accounting_settings (setting_key, account_id, description)
        SELECT
            'LOCATION_' || p.location_id || '_' || p.role,
            coa.id,
            'Direct COA from Finance workbook for location ' || p.location_id || ': ' || p.role
        FROM pairs p
        JOIN chart_of_accounts coa
          ON coa.account_number = p.account_number
         AND coa.is_active = true
         AND coa.is_posting = true
        ON CONFLICT (setting_key)
        DO UPDATE SET
            account_id = EXCLUDED.account_id,
            description = EXCLUDED.description
        """
    )


def downgrade() -> None:
    # Do not revert account activation or historical accounting. Remove only
    # the mapping keys introduced by this seed.
    op.execute(
        """
        DELETE FROM accounting_settings
        WHERE setting_key = 'INPUT_VAT_ACCOUNT'
           OR setting_key ~ '^LOCATION_[0-9]+_(AP|INVENTORY_FOOD|INVENTORY_BEVERAGE|INVENTORY_MATERIAL|AR|ACCRUAL|PETTY_CASH)$'
        """
    )
