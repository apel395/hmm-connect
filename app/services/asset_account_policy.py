"""MMH's supplied COA. Codes are resolved to database IDs, never inferred from IDs."""
ASSET_ACCOUNTS = {
    '100-600-100': ('Tanah', None),
    '100-600-101': ('Bangunan', '100-800-100'),
    '100-600-102': ('Mekanikal dan Elektrikal', '100-800-101'),
    '100-600-103': ('Kendaraan', '100-800-102'),
    '100-600-104': ('Furniture, Fixture and Equipment', '100-800-103'),
    '100-600-105': ('Inventaris', '100-800-104'),
    '100-600-999': ('Asset Tetap Lainnya', '100-800-999'),
}
DEPRECIATION_EXPENSE = '700-500-133'
