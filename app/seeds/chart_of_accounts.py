from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.accounting_posting_rule import AccountingPostingRule
from app.models.bank_account import BankAccount
from app.models.business_unit import BusinessUnit
from app.models.chart_of_account import ChartOfAccount


# Approved HMM Chart of Accounts supplied by Pak Ardi (COA.xlsx).
# Tuple fields:
# code, name, account_type, normal_balance, row_kind, account_subtype,
# cash_flow_category, financial_statement_group
DEFAULT_CHART_OF_ACCOUNTS = [('400', 'Gaji', 'REVENUE', 'CREDIT', 'PARENT', 'OTHER', 'OPERATING', 'OPERATING REVENUE'),
 ('400-100-100', 'Room Sales', 'REVENUE', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING REVENUE'),
 ('400-100-101', 'Food & Beverage', 'REVENUE', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING REVENUE'),
 ('400-100-102', 'Laundry', 'REVENUE', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING REVENUE'),
 ('400-100-103', 'Kolam renang', 'REVENUE', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING REVENUE'),
 ('400-100-104', 'Pusat Kegiatan Niaga', 'REVENUE', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING REVENUE'),
 ('400-100-105', 'Spa', 'REVENUE', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING REVENUE'),
 ('400-100-999', 'Pendapatan Lain-lain Hotel', 'REVENUE', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING REVENUE'),
 ('500', 'Beban Pokok Penjualan', 'EXPENSE', 'DEBIT', 'PARENT', 'OTHER', 'OPERATING', 'OPERATING REVENUE'),
 ('500-100-100', 'Beban Pokok Makanan', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'COST OF REVENUE'),
 ('500-100-101', 'Beban Pokok Langsung', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'COST OF REVENUE'),
 ('500-100-102', 'Beban Pokok Minuman', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'COST OF REVENUE'),
 ('500-100-999', 'Beban Pokok Lainnya', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'COST OF REVENUE'),
 ('600', 'Payroll', 'EXPENSE', 'DEBIT', 'PARENT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('600-100-100', 'Gaji', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('600-100-101', 'BPJS TK', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('600-100-102', 'BPJS Kes', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('600-100-103', 'Upah Pekerja Harian', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('600-100-104', 'THR', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('600-100-105', 'Kompensasi / Pesangon', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('600-100-106', 'PPH 21', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('600-100-107', 'Makan Karyawan', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('600-100-108', 'Tunjangan Cuti', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('600-100-999', 'Lainnya', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('700', 'Beban Operasional Lainnya', 'EXPENSE', 'DEBIT', 'PARENT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('700-500-100', 'Transportasi dan Perjalanan Dinas', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('700-500-101', 'Pakaian seragam', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('700-500-102', 'Entertainment', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('700-500-103', 'Alat Tulis Kantor (ATK)', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('700-500-104', 'Kebersihan dan Pest Control', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('700-500-105', 'Perbaikan dan Perawatan Kendaraan', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('700-500-106', 'Perbaikan Peralatan Operasional', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('700-500-107', 'Koran,Telepone,TV dan Internet', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('700-500-108', 'Alat Pemadam dan Keselamatan', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('700-500-109', 'Pajak Kendaraan', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('700-500-110', 'Pelatihan / Training', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('700-500-111', 'Pajak Iklan', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('700-500-112', 'Asuransi Gedung/Kendaraan', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('700-500-113', 'Pajak Bumi dan Bangunan', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('700-500-114', 'Pajak Reklame', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('700-500-115', 'Jasa Auditor', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('700-500-116', 'Jasa Konsultan', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('700-500-117', 'Jasa Notaris', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('700-500-118', 'Jasa Hukum', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('700-500-119', 'Sumbangan dan Sosial', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('700-500-120', 'Iklan,Promosi dan Marketing', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('700-500-121', 'Perangkat Lunak/Keras Komputer', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('700-500-122', 'Biaya Admin Bank', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('700-500-123', 'Biaya Materai', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('700-500-124', 'Biaya Kirim dan Pos', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('700-500-125', 'Biaya Perizinan', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('700-500-126', 'Biaya Rapat', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('700-500-127', 'Biaya Kesehatan', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('700-500-128', 'Biaya Rekrutmen', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('700-500-129', 'Biaya Listrik', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('700-500-130', 'Biaya Air', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('700-500-131', 'Biaya Gas', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('700-500-132', 'Biaya Solar', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('700-500-133', 'Biaya Service Charge', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('700-500-134', 'Lost and Brekage', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('700-500-135', 'Social, Sport and Activities', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('700-500-136', 'Biaya Management Fee', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('700-500-137', 'Biaya Management Fee Hotel', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('700-500-138', 'Biaya Management Fee Catering', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('700-500-139', 'Biaya PBJT', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('700-500-140', 'Biaya Pajak Lainnya', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('700-500-141', 'Biaya Operasional Lainnya', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('740', 'Beban Depresiasi dan Amortisasi', 'EXPENSE', 'DEBIT', 'PARENT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('740-100-100', 'Depresiasi Bangunan', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('740-100-101', 'Depresiasi Mekanikal dan Elektrikal', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('740-100-102', 'Depresiasi Kendaraan', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('740-100-103', 'Depresiasi Furniture, Fixture and Equipment', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('740-100-104', 'Depresiasi Asset Tetap Lainnya', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('740-100-105', 'Amortisasi', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('760', 'Pendapatan dan Beban Lainnya', '', 'DEBIT', 'PARENT', 'OTHER', 'OPERATING', 'OPERATING EXPENSES'),
 ('760-100-100', 'Pendapatan Bunga Bank', 'REVENUE', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OTHERS REVENUE'),
 ('760-100-101', 'Pendaptan Lain-lain', 'REVENUE', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OTHERS REVENUE'),
 ('760-100-102', 'Pajak Pendapatan Bunga Bank', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OTHERS EXPENSES'),
 ('760-100-103', 'Beban Bunga', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OTHERS EXPENSES'),
 ('760-100-104', 'Biaya korporasi', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OTHERS EXPENSES'),
 ('760-100-999', 'Biaya Lain-lainnya', 'EXPENSE', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'OTHERS EXPENSES'),
 ('100-100', 'KAS', 'ASSET', 'DEBIT', 'PARENT', 'PETTY_CASH', 'OPERATING', 'CURRENT_ASSET'),
 ('100-100-100', 'Petty Cash - Rumin', 'ASSET', 'DEBIT', 'ACCOUNT', 'PETTY_CASH', 'OPERATING', 'CURRENT_ASSET'),
 ('100-100-101', 'Petty Cash - Lipet', 'ASSET', 'DEBIT', 'ACCOUNT', 'PETTY_CASH', 'OPERATING', 'CURRENT_ASSET'),
 ('100-100-102', 'Petty Cash - Zamped', 'ASSET', 'DEBIT', 'ACCOUNT', 'PETTY_CASH', 'OPERATING', 'CURRENT_ASSET'),
 ('100-100-103', 'Petty Cash - General Cashier', 'ASSET', 'DEBIT', 'ACCOUNT', 'PETTY_CASH', 'OPERATING', 'CURRENT_ASSET'),
 ('100-100-104', 'Petty Cash - FO Cashier', 'ASSET', 'DEBIT', 'ACCOUNT', 'PETTY_CASH', 'OPERATING', 'CURRENT_ASSET'),
 ('100-100-105', 'Petty Cash - FB Cashier', 'ASSET', 'DEBIT', 'ACCOUNT', 'PETTY_CASH', 'OPERATING', 'CURRENT_ASSET'),
 ('100-100-106', 'Petty Cash - PHM', 'ASSET', 'DEBIT', 'ACCOUNT', 'PETTY_CASH', 'OPERATING', 'CURRENT_ASSET'),
 ('100-100-107', 'Petty Cash - Head Office Catering', 'ASSET', 'DEBIT', 'ACCOUNT', 'PETTY_CASH', 'OPERATING', 'CURRENT_ASSET'),
 ('100-100-108', 'Petty Cash - Mc Delmot Batam', 'ASSET', 'DEBIT', 'ACCOUNT', 'PETTY_CASH', 'OPERATING', 'CURRENT_ASSET'),
 ('100-100-109', 'Petty Cash - Duri', 'ASSET', 'DEBIT', 'ACCOUNT', 'PETTY_CASH', 'OPERATING', 'CURRENT_ASSET'),
 ('100-100-110', 'Petty Cash - Sanga-Sanga', 'ASSET', 'DEBIT', 'ACCOUNT', 'PETTY_CASH', 'OPERATING', 'CURRENT_ASSET'),
 ('100-100-111', 'Petty Cash - Rockhan Café', 'ASSET', 'DEBIT', 'ACCOUNT', 'PETTY_CASH', 'OPERATING', 'CURRENT_ASSET'),
 ('100-100-112', 'Petty Cash - Hulu Cafe', 'ASSET', 'DEBIT', 'ACCOUNT', 'PETTY_CASH', 'OPERATING', 'CURRENT_ASSET'),
 ('100-100-990', 'Petty Cash - Belum Realisasi', 'ASSET', 'DEBIT', 'ACCOUNT', 'PETTY_CASH', 'OPERATING', 'CURRENT_ASSET'),
 ('100-110', 'BANK', 'ASSET', 'DEBIT', 'PARENT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-110-100', 'Bank Mandiri 108-001-2525250', 'ASSET', 'DEBIT', 'ACCOUNT', 'BANK', 'OPERATING', 'CURRENT_ASSET'),
 ('100-110-101', 'Bank Mandiri 108-005-3252525', 'ASSET', 'DEBIT', 'ACCOUNT', 'BANK', 'OPERATING', 'CURRENT_ASSET'),
 ('100-110-102', 'Bank Mandiri 108-002-5915225', 'ASSET', 'DEBIT', 'ACCOUNT', 'BANK', 'OPERATING', 'CURRENT_ASSET'),
 ('100-110-103', 'Bank BNI 193-684771', 'ASSET', 'DEBIT', 'ACCOUNT', 'BANK', 'OPERATING', 'CURRENT_ASSET'),
 ('100-110-104', 'Bank BSI 700-372-4667', 'ASSET', 'DEBIT', 'ACCOUNT', 'BANK', 'OPERATING', 'CURRENT_ASSET'),
 ('100-110-105', 'Bank Bukopin 100-3488221', 'ASSET', 'DEBIT', 'ACCOUNT', 'BANK', 'OPERATING', 'CURRENT_ASSET'),
 ('100-110-106', 'Bank BRI 107-901000207301', 'ASSET', 'DEBIT', 'ACCOUNT', 'BANK', 'OPERATING', 'CURRENT_ASSET'),
 ('100-110-107', 'Bank BRK 149-0800353', 'ASSET', 'DEBIT', 'ACCOUNT', 'BANK', 'OPERATING', 'CURRENT_ASSET'),
 ('100-110-108', 'Bank BNI 779-84697', 'ASSET', 'DEBIT', 'ACCOUNT', 'BANK', 'OPERATING', 'CURRENT_ASSET'),
 ('100-110-109', 'Bank BNI 779-84686', 'ASSET', 'DEBIT', 'ACCOUNT', 'BANK', 'OPERATING', 'CURRENT_ASSET'),
 ('100-110-110', 'Bank Mandiri 108-007-4121212', 'ASSET', 'DEBIT', 'ACCOUNT', 'BANK', 'OPERATING', 'CURRENT_ASSET'),
 ('100-110-111', 'Bank BRK 101-080-8332', 'ASSET', 'DEBIT', 'ACCOUNT', 'BANK', 'OPERATING', 'CURRENT_ASSET'),
 ('100-110-112', 'Bank Mega 010-540-011001943', 'ASSET', 'DEBIT', 'ACCOUNT', 'BANK', 'OPERATING', 'CURRENT_ASSET'),
 ('100-110-113', 'MayBank 278-6000600', 'ASSET', 'DEBIT', 'ACCOUNT', 'BANK', 'OPERATING', 'CURRENT_ASSET'),
 ('100-110-114', 'Bank BCA 034-202-2225', 'ASSET', 'DEBIT', 'ACCOUNT', 'BANK', 'OPERATING', 'CURRENT_ASSET'),
 ('100-110-115', 'Bank Mandiri 108-008-2212128', 'ASSET', 'DEBIT', 'ACCOUNT', 'BANK', 'OPERATING', 'CURRENT_ASSET'),
 ('100-110-116', 'Bank Mandiri 108-007-0025250', 'ASSET', 'DEBIT', 'ACCOUNT', 'BANK', 'OPERATING', 'CURRENT_ASSET'),
 ('100-110-117', 'Bank Mandiri 108-052-5000205', 'ASSET', 'DEBIT', 'ACCOUNT', 'BANK', 'OPERATING', 'CURRENT_ASSET'),
 ('100-110-118', 'Bank Mandiri 108-052-5000304', 'ASSET', 'DEBIT', 'ACCOUNT', 'BANK', 'OPERATING', 'CURRENT_ASSET'),
 ('100-110-119', 'Bank Mandiri 108-052-5000106', 'ASSET', 'DEBIT', 'ACCOUNT', 'BANK', 'OPERATING', 'CURRENT_ASSET'),
 ('100-110-120', 'Bank BTN 006-520-1300000650', 'ASSET', 'DEBIT', 'ACCOUNT', 'BANK', 'OPERATING', 'CURRENT_ASSET'),
 ('100-110-121', 'Bank Mandiri 108-008-0252522', 'ASSET', 'DEBIT', 'ACCOUNT', 'BANK', 'OPERATING', 'CURRENT_ASSET'),
 ('100-110-122', 'Bank Mandiri 108-007-2252522', 'ASSET', 'DEBIT', 'ACCOUNT', 'BANK', 'OPERATING', 'CURRENT_ASSET'),
 ('100-110-123', 'Bank Mandiri 108.007-9252525', 'ASSET', 'DEBIT', 'ACCOUNT', 'BANK', 'OPERATING', 'CURRENT_ASSET'),
 ('100-120', 'CLEARANCE ACCOUNT', 'ASSET', 'DEBIT', 'PARENT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-120-100', 'Kas Penjualan - Clearance', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-120-101', 'Hutang - Clearance', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-120-102', 'Piutang - Clearance', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-120-103', 'Petty Cash - Clearance', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-120-104', 'Cash Sales Hulu Cafe - Clearance', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-120-105', 'Cash Sales PHM - Clearance', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-120-106', 'Cash Sales MC DELLMOT BATAM - Clearance', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-120-107', 'Cash Sales PHR DURI - Clearance', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-120-999', 'Others - Clearance', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-130', 'IN TRANSIT ACCOUNT', 'ASSET', 'DEBIT', 'PARENT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-130-100', 'Cash In Transit Penjualan', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-130-101', 'Transitory Transaksi - GDSK', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-200', 'PIUTANG USAHA', 'ASSET', 'DEBIT', 'PARENT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-200-100', 'Guest Ledger', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-200-101', 'Piutang Usaha / AR', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-200-102', 'Piutang Usaha - Hotel', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-200-103', 'Piutang Usaha - PHR Libo Petapahan', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-200-104', 'Piutang Usaha - BSP Zamrud Pedada', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-200-105', 'Piutang Usaha - PHR Rumbai Minas', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-200-106', 'Piutang Usaha - PHM Balikpapan', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-200-107', 'Piutang Usaha - PEP Sanga-sanga', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-200-108', 'Piutang Usaha - MC Dellmott', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-200-109', 'Piutang Usaha - PHR Duri', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-200-110', 'Piutang Usaha - PHKT', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-200-111', 'Piutang Usaha - PRCC', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-200-999', 'Piutang Usaha Lainnya', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-210', 'PIUTANG USAHA LAINNYA', 'ASSET', 'DEBIT', 'PARENT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-210-100', 'Piutang Affiliasi', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-210-101', 'Pinjaman Karyawan', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-210-102', 'Piutang Direksi', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-210-103', 'Deposit Pembelian', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-210-104', 'Jaminan Pelaksanaan Kontrak', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-210-999', 'Piutang Lainnya', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-300', 'PERSEDIAAN', 'ASSET', 'DEBIT', 'PARENT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-300-100', 'Inv Makanan - Hotel', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-300-101', 'Inv Makanan - PHR Libo Petapahan', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-300-102', 'Inv Makanan - BSP Zamrud Pedada', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-300-103', 'Inv Makanan - PHR Rumbai Minas', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-300-104', 'Inv Makanan - PHM Balikpapan', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-300-105', 'Inv Makanan - PEP Sanga-sanga', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-300-106', 'Inv Makanan - MC Dellmott Batam', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-300-107', 'Inv Makanan - PHR Duri', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-300-108', 'Inv Makanan - PHKT', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-300-109', 'Inv Makanan - PRCC', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-300-500', 'Inv - Minuman - Hotel', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-300-501', 'Inv - Minuman - PHR Libo Petapahan', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-300-502', 'Inv - Minuman - BSP Zamrud Pedada', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-300-503', 'Inv - Minuman - PHR Rumbai Minas', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-300-504', 'Inv - Minuman - PHM Balikpapan', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-300-505', 'Inv - Minuman - PEP Sanga-sanga', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-300-506', 'Inv - Minuman - Mc Delmott Batam', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-300-507', 'Inv - Minuman - PHR Duri', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-300-508', 'Inv - Minuman - PHKT', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-300-509', 'Inv - Minuman - PRCC', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-300-700', 'Inv - Material - Hotel', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-300-701', 'Inv - Material - PHR Libo Petapahan', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-300-702', 'Inv - Material - BSP Zamrud Pedada', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-300-703', 'Inv - Material - PHR Rumbai Minas', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-300-704', 'Inv - Material - PHM Balikpapan', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-300-705', 'Inv - Material - PEP Sanga sanga', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-300-706', 'Inv - Material - Mc Delmott Batam', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-300-707', 'Inv - Material - PHR Duri', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-300-708', 'Inv - Material - PHKT', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-300-709', 'Inv - Material - PRCC', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-300-800', 'Persedian Bahan Bakar', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-300-999', 'Persedian Lainnya', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-400', 'BIAYA DIBAYAR DIMUKA', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-400-100', 'Asuransi - Mobil', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-400-101', 'Asuransi - Gedung', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-400-102', 'Pajak Reklame', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-400-103', 'Pajak Kendaraan', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-400-104', 'Pajak Bumi dan Bangunan', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-400-105', 'Asuransi Kontrak Kerja', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-400-106', 'Kantor', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-500', 'PAJAK DIBAYAR DIMUKA', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-500-100', 'Pajak Ppn Masukan', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-500-101', 'Pajak PPH 25', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-500-102', 'Pajak PPH 23', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-500-103', 'Pajak PPH 29', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-500-104', 'Pajak PPH 21', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-600', 'ASSET TETAP', 'ASSET', 'DEBIT', 'PARENT', 'OTHER', 'OPERATING', 'CURRENT_ASSET'),
 ('100-600-100', 'Tanah', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'NON CURRENT_ASSET'),
 ('100-600-101', 'Bangunan', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'NON CURRENT_ASSET'),
 ('100-600-102', 'Mekanikal dan Elektrikal', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'NON CURRENT_ASSET'),
 ('100-600-103', 'Kendaraan', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'NON CURRENT_ASSET'),
 ('100-600-104', 'Furniture, Fixture and Equipment', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'NON CURRENT_ASSET'),
 ('100-600-105', 'Asset Tetap Lainnya', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'NON CURRENT_ASSET'),
 ('100-700', 'PROJECT ON PROGRESS', 'ASSET', 'DEBIT', 'PARENT', 'OTHER', 'OPERATING', 'NON CURRENT_ASSET'),
 ('100-700-100', 'Bangunan dalam Penyelesaian', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'NON CURRENT_ASSET'),
 ('100-700-101', 'Pra Operasi Project', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'NON CURRENT_ASSET'),
 ('100-800', 'AKUMULASI DEPRESIASI', 'ASSET', 'DEBIT', 'PARENT', 'OTHER', 'OPERATING', 'NON CURRENT_ASSET'),
 ('100-800-100', 'Akumulasi Depresiasi - Bangunan', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'NON CURRENT_ASSET'),
 ('100-800-101', 'Akumulasi Depresiasi - Mekanikal dan Elektrikal', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'NON CURRENT_ASSET'),
 ('100-800-102', 'Akumulasi Depresiasi - Kendaraan', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'NON CURRENT_ASSET'),
 ('100-800-103', 'Akumulasi Depresiasi - FF&E', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'NON CURRENT_ASSET'),
 ('100-800-104', 'Akumulasi Depresiasi - Asset Tetap Lainnya', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'NON CURRENT_ASSET'),
 ('100-900', 'PERALATAN OPERASIONAL', 'ASSET', 'DEBIT', 'PARENT', 'OTHER', 'OPERATING', 'NON CURRENT_ASSET'),
 ('100-900-100', 'Opr Equipment - Linen', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'NON CURRENT_ASSET'),
 ('100-900-101', 'Opr Equipment - Chinessware', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'NON CURRENT_ASSET'),
 ('100-900-102', 'Opr Equipment - Silverware', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'NON CURRENT_ASSET'),
 ('100-900-103', 'Opr Equipment - Glassware', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'NON CURRENT_ASSET'),
 ('100-900-104', 'Opr Equipment - Glassware', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'NON CURRENT_ASSET'),
 ('101-100', 'Penyertaan Saham', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'NON CURRENT_ASSET'),
 ('101-100-100', 'Penyertaan Saham Bank BPR Khasanah', 'ASSET', 'DEBIT', 'ACCOUNT', 'OTHER', 'INVESTING', 'NON CURRENT_ASSET'),
 ('200-100', 'HUTANG USAHA', 'LIABILITY', 'CREDIT', 'PARENT', 'OTHER', 'OPERATING', 'CURRENT_LIABILITY'),
 ('200-100-1', 'Hutang Usaha - Hotel', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_LIABILITY'),
 ('200-100-2', 'Hutang Usaha - PHR Libo Petapahan', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_LIABILITY'),
 ('200-100-3', 'Hutang Usaha - BSP Zamrud Pedada', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_LIABILITY'),
 ('200-100-4', 'Hutang Usaha - PHR Rumbai Minas', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_LIABILITY'),
 ('200-100-5', 'Hutang Usaha - PHM Balikpapan', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_LIABILITY'),
 ('200-100-6', 'Hutang Usaha - PEP Sanga-sanga', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_LIABILITY'),
 ('200-100-7', 'Hutang Usaha - MC Dellmott', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_LIABILITY'),
 ('200-100-8', 'Hutang Usaha - PHR Duri', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_LIABILITY'),
 ('200-100-9', 'Hutang Usaha - PHKT', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_LIABILITY'),
 ('200-100-10', 'Hutang Usaha - PRCC', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_LIABILITY'),
 ('200-200', 'BIAYA ACCRUAL', 'LIABILITY', 'CREDIT', 'PARENT', 'OTHER', 'OPERATING', 'CURRENT_LIABILITY'),
 ('200-200-100', 'Accrual Gaji - Hotel', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_LIABILITY'),
 ('200-200-101', 'Accrual Gaji - PHR Libo Petapahan', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_LIABILITY'),
 ('200-200-102', 'Accrual Gaji - BSP Zamrud Pedada', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_LIABILITY'),
 ('200-200-103', 'Accrual Gaji - PHR Rumbai Minas', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_LIABILITY'),
 ('200-200-104', 'Accrual Gaji - PHM Balikpapan', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_LIABILITY'),
 ('200-200-105', 'Accrual Gaji - PEP Sanga-sanga', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_LIABILITY'),
 ('200-200-106', 'Accrual Gaji - MC Dellmott', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_LIABILITY'),
 ('200-200-107', 'Accrual Gaji - PHR Duri', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_LIABILITY'),
 ('200-200-108', 'Accrual Gaji - PHKT', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_LIABILITY'),
 ('200-200-109', 'Accrual Gaji - Head Office Catering', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_LIABILITY'),
 ('200-200-110', 'Accrual - THR', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_LIABILITY'),
 ('200-200-111', 'Accrual - Kompensasi', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_LIABILITY'),
 ('200-200-112', 'Accrual - BPJS Kesehatan', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_LIABILITY'),
 ('200-200-113', 'Accrual - BPJS Ketenaga Kerjaan', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_LIABILITY'),
 ('200-200-114', 'Accrual - Biaya Listrik', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_LIABILITY'),
 ('200-200-115', 'Accrual - Asuransi Pekerja Lainnya', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_LIABILITY'),
 ('200-200-116', 'Accrual - Service Charge', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_LIABILITY'),
 ('200-200-117', 'Accrual - Lost and Brekage', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_LIABILITY'),
 ('200-200-118', 'Accrual - Social, Sport and Activities', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_LIABILITY'),
 ('200-200-999', 'Accrual - Lainnya', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'CURRENT_LIABILITY'),
 ('200-300', 'HUTANG JANGKA PENDEK', 'LIABILITY', 'CREDIT', 'PARENT', 'OTHER', 'OPERATING', 'NON CURRENT_LIABILITY'),
 ('200-300-100', 'KMK Revolving - Mandiri 1 M', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'FINANCING', 'NON CURRENT_LIABILITY'),
 ('200-300-101', 'KMK Non Revolving - Mandiri 1.3 M Aflopend II', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'FINANCING', 'NON CURRENT_LIABILITY'),
 ('200-300-102', 'KMK Non Revolving - Mandiri 2.4 M Aflopend III', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'FINANCING', 'NON CURRENT_LIABILITY'),
 ('200-300-103', 'KMK Non Revolving - Mandiri 3.5 M Aflopend I', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'FINANCING', 'NON CURRENT_LIABILITY'),
 ('200-300-104', 'Hutang Bank - Mandiri Invoicing', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'FINANCING', 'NON CURRENT_LIABILITY'),
 ('200-300-105', 'Hutang Leasing', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'FINANCING', 'NON CURRENT_LIABILITY'),
 ('200-300-106', 'Hutang Deposit Tamu', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'NON CURRENT_LIABILITY'),
 ('200-300-999', 'Hutang Lainnya', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'NON CURRENT_LIABILITY'),
 ('200-400', 'HUTANG PAJAK', 'LIABILITY', 'CREDIT', 'PARENT', 'OTHER', 'OPERATING', 'NON CURRENT_LIABILITY'),
 ('200-400-100', 'Hutang PBJT - Hotel dan Resto, Catering', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'NON CURRENT_LIABILITY'),
 ('200-400-101', 'Hutang PBJT - Listrik', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'NON CURRENT_LIABILITY'),
 ('200-400-102', 'Hutang Pajak PPH 21', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'NON CURRENT_LIABILITY'),
 ('200-400-103', 'Hutang Pajak PPH 23', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'NON CURRENT_LIABILITY'),
 ('200-400-104', 'Hutang Pajak PPH 25', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'NON CURRENT_LIABILITY'),
 ('200-400-105', 'Hutang Pajak PPH Pasal 4', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'NON CURRENT_LIABILITY'),
 ('200-400-106', 'Hutang PPn Keluaran', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'NON CURRENT_LIABILITY'),
 ('200-400-107', 'Hutang Pajak Air Bawah tanah', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'NON CURRENT_LIABILITY'),
 ('200-400-108', 'Hutang Pajak PPH 29', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'NON CURRENT_LIABILITY'),
 ('200-500-100', 'Pendapatan Sewa ATM BTN', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'NON CURRENT_LIABILITY'),
 ('200-500-101', 'Pendapatan Sewa Telkomsel', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'NON CURRENT_LIABILITY'),
 ('200-500-102', 'Pendapatan Sewa Gas Indonesia', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'NON CURRENT_LIABILITY'),
 ('200-500-103', 'Pendapatan Sewa Global Teknologi', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'NON CURRENT_LIABILITY'),
 ('200-500-999', 'Pendapatan Sewa Lainnya', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'NON CURRENT_LIABILITY'),
 ('200-600', 'Hutang Affiliasi', 'LIABILITY', 'CREDIT', 'PARENT', 'OTHER', 'OPERATING', 'NON CURRENT_LIABILITY'),
 ('200-600-100', 'Hutang Affiliasi - PT. Mona Rimbo Panjang', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'NON CURRENT_LIABILITY'),
 ('200-600-101', 'Hutang Affiliasi - Direksi', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'NON CURRENT_LIABILITY'),
 ('200-600-102', 'Hutang Affiliasi - PT. Rizanindo', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'NON CURRENT_LIABILITY'),
 ('200-600-103', 'Hutang Affiliasi - PT. Rizanindo - Kendaraan', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'NON CURRENT_LIABILITY'),
 ('200-600-104', 'Hutang Affiliasi - SPBU Mona Rimbo Panjang (Bank)', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'NON CURRENT_LIABILITY'),
 ('200-600-105', 'Hutang Affiliasi - SPBU Mona Rimbo Panjang (Renovasi)', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'NON CURRENT_LIABILITY'),
 ('200-600-106', 'Hutang Affiliasi - PT. Mona Rimbo Panjang', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'NON CURRENT_LIABILITY'),
 ('200-700', 'HUTANG JANGKA PANJANG', 'LIABILITY', 'CREDIT', 'PARENT', 'OTHER', 'OPERATING', 'NON CURRENT_LIABILITY'),
 ('200-700-100', 'KMK Revolving - Mandiri 1 M', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'FINANCING', 'NON CURRENT_LIABILITY'),
 ('200-700-101', 'KMK Non Revolving - Mandiri 1.3 M Aflopend II', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'FINANCING', 'NON CURRENT_LIABILITY'),
 ('200-700-102', 'KMK Non Revolving - Mandiri 2.4 M Aflopend III', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'FINANCING', 'NON CURRENT_LIABILITY'),
 ('200-700-103', 'KMK Non Revolving - Mandiri 3.5 M Aflopend I', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'FINANCING', 'NON CURRENT_LIABILITY'),
 ('200-700-104', 'Hutang Bank - Mandiri KI', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'FINANCING', 'NON CURRENT_LIABILITY'),
 ('200-700-105', 'Hutang Leasing', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'FINANCING', 'NON CURRENT_LIABILITY'),
 ('200-700-106', 'Hutang Lainnya', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'FINANCING', 'NON CURRENT_LIABILITY'),
 ('200-800', 'IMBALAN PASCA KERJA', 'LIABILITY', 'CREDIT', 'PARENT', 'OTHER', 'OPERATING', 'NON CURRENT_LIABILITY'),
 ('200-800-100', 'Pesangon', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'NON CURRENT_LIABILITY'),
 ('200-800-101', 'Pensiun', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'NON CURRENT_LIABILITY'),
 ('200-800-102', 'Imbalan Lainnya', 'LIABILITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'NON CURRENT_LIABILITY'),
 ('300-100', 'EQUITY', 'EQUITY', 'CREDIT', 'PARENT', 'OTHER', 'OPERATING', 'EQUITY'),
 ('300-100-100', 'Modal Awal Disetor', 'EQUITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'EQUITY'),
 ('300-100-101', 'Tambahan Modal Disetor (TA)', 'EQUITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'EQUITY'),
 ('300-100-102', 'Laba/Rugi Ditahan', 'EQUITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'EQUITY'),
 ('300-100-103', 'Laba/Rugi Ditahan Tahun Berjalan', 'EQUITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'EQUITY'),
 ('300-100-104', 'Prive / Penarikan Modal', 'EQUITY', 'CREDIT', 'ACCOUNT', 'OTHER', 'OPERATING', 'EQUITY')]

PETTY_CASH_BUSINESS_UNITS = {'100-100-100': 'Project Catering', '100-100-101': 'Project Catering', '100-100-102': 'Project Catering', '100-100-103': 'Hotel', '100-100-104': 'Hotel', '100-100-105': 'Hotel', '100-100-106': 'Project Catering', '100-100-107': 'Project Catering', '100-100-108': 'Project Catering', '100-100-109': 'Project Catering', '100-100-110': 'Project Catering', '100-100-111': 'Hotel', '100-100-112': 'Hotel', '100-100-990': 'Hotel'}

INPUT_VAT_ACCOUNT_NUMBER = "100-500-100"
INPUT_VAT_EVENTS = ("SUPPLIER_INVOICE_INVENTORY", "SUPPLIER_INVOICE_DIRECT_USE")


def _parent_number(code: str, available: set[str]) -> str | None:
    parts = code.split("-")
    for size in range(len(parts) - 1, 0, -1):
        candidate = "-".join(parts[:size])
        if candidate in available:
            return candidate
    return None


def seed_chart_of_accounts(db: Session) -> dict[str, int]:
    existing = {row.account_number: row for row in db.query(ChartOfAccount).all()}
    source_codes = {row[0] for row in DEFAULT_CHART_OF_ACCOUNTS}
    available_codes = set(existing) | source_codes
    created: dict[str, ChartOfAccount] = {}
    skipped = 0

    for code, name, account_type, normal_balance, row_kind, subtype, cash_flow, fs_group in sorted(
        DEFAULT_CHART_OF_ACCOUNTS, key=lambda row: (row[0].count("-"), row[0])
    ):
        if code in existing:
            skipped += 1
            continue
        account = ChartOfAccount(
            account_number=code,
            account_name=name,
            account_type=account_type or "ASSET",
            normal_balance=normal_balance,
            cash_flow_category=cash_flow,
            account_subtype=subtype or "OTHER",
            financial_statement_group=fs_group,
            is_posting=(row_kind == "ACCOUNT"),
            is_system=False,
            is_active=True,
        )
        db.add(account)
        db.flush()
        existing[code] = account
        created[code] = account

    for code, account in created.items():
        parent = _parent_number(code, available_codes)
        if parent and parent in existing:
            account.parent_account_id = existing[parent].id
    return {"created": len(created), "existing_untouched": skipped}


def _business_unit(db: Session, name: str) -> BusinessUnit | None:
    return db.query(BusinessUnit).filter(BusinessUnit.name.ilike(name)).first()


def seed_cash_accounts(db: Session) -> dict[str, object]:
    created = 0
    existing_count = 0
    unresolved: list[str] = []
    for code, business_unit_name in PETTY_CASH_BUSINESS_UNITS.items():
        coa = db.query(ChartOfAccount).filter(ChartOfAccount.account_number == code).first()
        if not coa:
            unresolved.append(f"{code}: COA missing")
            continue
        if db.query(BankAccount).filter(BankAccount.coa_account_id == coa.id).first():
            existing_count += 1
            continue
        business_unit = _business_unit(db, business_unit_name)
        if not business_unit:
            unresolved.append(f"{code}: Business Unit '{business_unit_name}' not found")
            continue
        db.add(BankAccount(bank_name="Cash", account_name=coa.account_name, account_number=code, account_holder=None, currency="IDR", business_unit_id=business_unit.id, location_id=None, coa_account_id=coa.id, is_active=True))
        created += 1
    return {"created": created, "existing_untouched": existing_count, "unresolved": unresolved}


def seed_input_vat_posting(db: Session) -> dict[str, object]:
    account = db.query(ChartOfAccount).filter(ChartOfAccount.account_number == INPUT_VAT_ACCOUNT_NUMBER).first()
    if not account:
        return {"configured": 0, "missing": [f"COA {INPUT_VAT_ACCOUNT_NUMBER}"]}
    configured = 0
    missing: list[str] = []
    for event_type in INPUT_VAT_EVENTS:
        rule = db.query(AccountingPostingRule).filter(AccountingPostingRule.event_type == event_type, AccountingPostingRule.is_active.is_(True)).first()
        if not rule:
            missing.append(event_type)
            continue
        if rule.input_vat_account_id is None:
            rule.input_vat_account_id = account.id
            configured += 1
    return {"configured": configured, "missing": missing}
