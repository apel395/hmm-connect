from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ItemClass:
    group_code: str
    group_name: str
    subgroup_code: str
    subgroup_name: str


# Source of truth: Book1.xlsx / SETUP / SETUP KELOMPOK BARANG.
ITEM_CLASSES = {
    "1-1": ItemClass("1", "FOOD", "1-1", "MEAT"),
    "1-2": ItemClass("1", "FOOD", "1-2", "POULTRY"),
    "1-3": ItemClass("1", "FOOD", "1-3", "FISH"),
    "1-4": ItemClass("1", "FOOD", "1-4", "SEAFOOD"),
    "1-5": ItemClass("1", "FOOD", "1-5", "VEGETABLES"),
    "1-6": ItemClass("1", "FOOD", "1-6", "FRUIT"),
    "1-7": ItemClass("1", "FOOD", "1-7", "HERB"),
    "1-8": ItemClass("1", "FOOD", "1-8", "GRESORIS"),
    "1-9": ItemClass("1", "FOOD", "1-9", "SNACK"),
    "2-1": ItemClass("2", "BEVERAGE", "2-1", "MINERAL WATER"),
    "2-2": ItemClass("2", "BEVERAGE", "2-2", "SOFT DRINK"),
    "2-3": ItemClass("2", "BEVERAGE", "2-3", "BEER"),
    "2-4": ItemClass("2", "BEVERAGE", "2-4", "WINE"),
    "2-5": ItemClass("2", "BEVERAGE", "2-5", "LIQUER"),
    "2-6": ItemClass("2", "BEVERAGE", "2-6", "VODKA"),
    "3-1": ItemClass("3", "MATERIAL", "3-1", "GUEST SUPPLIES"),
    "3-2": ItemClass("3", "MATERIAL", "3-2", "CLEANING SUPPLIES"),
    "3-3": ItemClass("3", "MATERIAL", "3-3", "PRINTING"),
    "3-4": ItemClass("3", "MATERIAL", "3-4", "STATIONARY"),
    "3-5": ItemClass("3", "MATERIAL", "3-5", "MARKETING"),
    "3-6": ItemClass("3", "MATERIAL", "3-6", "GASOLINE"),
    "4-1": ItemClass("4", "ASSET", "4-1", "BUILDING"),
    "4-2": ItemClass("4", "ASSET", "4-2", "FURNITURE"),
    "4-3": ItemClass("4", "ASSET", "4-3", "MACHINERY"),
    "4-4": ItemClass("4", "ASSET", "4-4", "KOMPUTER"),
    "4-5": ItemClass("4", "ASSET", "4-5", "VEHICLE"),
}

# Order matters: specific classes precede general grocery/consumable terms.
KEYWORDS = {
    "2-6": ("VODKA",),
    "2-4": ("WINE", "MERLOT", "CABERNET", "CHARDONNAY"),
    "2-3": ("BEER", "BIR ", "BINTANG"),
    "2-5": ("LIQUOR", "LIQUEUR", "WHISKY", "WHISKEY", "RUM ", "GIN ", "TEQUILA"),
    "2-1": ("MINERAL WATER", "AQUA", "LE MINERALE", "AIR MINERAL"),
    "2-2": ("COCA COLA", "FANTA", "SPRITE", "SODA", "SOFT DRINK", "TONIC WATER"),
    "1-4": ("UDANG", "SHRIMP", "CUMI", "SQUID", "KEPITING", "CRAB", "KERANG", "LOBSTER", "SEAFOOD"),
    "1-3": ("IKAN", "FISH", "DORI", "TUNA", "SALMON", "KAKAP", "GURAME", "NILA", "PATIN", "LELE", "BANDENG", "TERI", "EBI"),
    "1-2": ("AYAM", "CHICKEN", "BEBEK", "DUCK"),
    "1-1": ("DAGING", "BEEF", "SAPI", "TENDERLOIN", "SIRLOIN", "KAMBING", "LAMB", "MUTTON"),
    "1-5": ("BAYAM", "KANGKUNG", "SAWI", "PAKCOY", "WORTEL", "KUBIS", "KOL ", "BUNCIS", "KACANG PANJANG", "TAUGE", "TOGE", "TIMUN", "MENTIMUN", "TERONG", "LABU", "OYONG", "GAMBAS", "PARE", "BROKOLI", "SELADA", "LETTUCE", "PAPRIKA", "TOMAT", "KAILAN", "CAISIM", "PETSAI", "LOBAK", "REbung", "JAGUNG MUDA"),
    "1-6": ("APEL", "APPLE", "JERUK", "ORANGE", "PISANG", "BANANA", "SEMANGKA", "WATERMELON", "MELON", "PEPAYA", "PAPAYA", "NANAS", "PINEAPPLE", "MANGGA", "MANGO", "ANGGUR", "GRAPE", "STRAWBERRY", "ALPUKAT", "AVOCADO"),
    "1-7": ("BAWANG", "GARLIC", "ONION", "JAHE", "GINGER", "KUNYIT", "TURMERIC", "LENGKUAS", "SEREH", "SERAI", "DAUN SALAM", "DAUN JERUK", "KEMANGI", "SELEDRI", "CELERY", "MERICA", "PEPPER", "KETUMBAR", "CORIANDER", "KAYU MANIS", "CINNAMON", "CENGKEH", "CLOVE", "PALA", "NUTMEG", "KAPULAGA", "CARDAMOM"),
    "1-9": ("SNACK", "KUE", "CAKE", "ROTI", "BREAD", "PASTRY", "LEMPER", "PEYEK", "BISKUIT", "BISCUIT", "COOKIE", "DONAT", "DONUT"),
    "3-2": ("DETERGENT", "DETERJEN", "CLEANER", "PEMBERSIH", "DISINFECT", "SABUN CUCI", "BLEACH", "KARBOL", "PEWANGI", "CHEMICAL"),
    "3-1": ("TISSUE", "TISU", "TOILETRIES", "SHAMPOO", "TOOTHBRUSH", "PASTA GIGI", "SLIPPER", "AMENITIES", "NAPKIN"),
    "3-3": ("PRINT", "PRINTING", "TONER", "CARTRIDGE", "INK", "TINTA"),
    "3-4": ("KERTAS", "PAPER", "PULPEN", "PEN ", "PENCIL", "PENSIL", "MAP ", "FOLDER", "STAPLER", "CLIP", "ENVELOPE", "AMPLOP", "NOTEBOOK", "ATK", "STATIONERY", "STATIONARY"),
    "3-5": ("BANNER", "SPANDUK", "BROCHURE", "BROSUR", "FLYER", "MARKETING", "PROMO"),
    "3-6": ("BENSIN", "PERTALITE", "PERTAMAX", "SOLAR", "DIESEL", "GASOLINE", "FUEL"),
    "4-4": ("LAPTOP", "COMPUTER", "KOMPUTER", "MONITOR", "PRINTER", "SERVER", "ROUTER", "UPS ", "KEYBOARD", "MOUSE"),
    "4-5": ("MOBIL", "CAR ", "MOTOR", "MOTORCYCLE", "VEHICLE", "BAN MOBIL", "TYRE", "TIRE"),
    "4-2": ("MEJA", "TABLE", "KURSI", "CHAIR", "LEMARI", "CABINET", "SOFA", "BED ", "MATTRESS", "FURNITURE"),
    "4-3": ("MACHINE", "MESIN", "PUMP", "POMPA", "GENSET", "COMPRESSOR", "CHILLER", "FREEZER", "OVEN"),
    "4-1": ("BUILDING", "BANGUNAN", "RENOVASI", "RENOVATION", "PINTU", "DOOR", "JENDELA", "WINDOW", "ATAP", "ROOF", "KERAMIK", "TILE", "SEMEN", "CEMENT"),
    "1-8": ("BERAS", "RICE", "TEPUNG", "FLOUR", "GULA", "SUGAR", "GARAM", "SALT", "MINYAK", "OIL", "KECAP", "SAUCE", "SAUS", "SUSU", "MILK", "TELUR", "EGG", "MIE", "NOODLE", "MENTEGA", "BUTTER", "MARGARIN", "KEJU", "CHEESE", "KOPI", "COFFEE", "TEH", "TEA", "SANTAN", "COCONUT MILK", "KACANG", "COKLAT", "CHOCOLATE"),
}


def normalize(value: object) -> str:
    return re.sub(r"[^A-Z0-9]+", " ", str(value or "").upper()).strip()


def class_from_product(product) -> ItemClass | None:
    subgroup_code = str(getattr(product, "subgroup_code", "") or "").strip()
    if subgroup_code in ITEM_CLASSES:
        return ITEM_CLASSES[subgroup_code]
    subgroup_name = normalize(getattr(product, "subgroup_name", ""))
    group_name = normalize(getattr(product, "group_name", ""))
    for item_class in ITEM_CLASSES.values():
        if normalize(item_class.subgroup_name) == subgroup_name and normalize(item_class.group_name) == group_name:
            return item_class
    return None


def infer_class(name: object) -> ItemClass:
    """Return an XLS taxonomy class for every historical Purchasing item.

    Historical PIM rows were inserted without their original taxonomy. We recover
    the obvious subgroup from the item name. The remaining generic consumables
    fall back to FOOD/GRESORIS (1-8), which is the XLS catch-all consumable class.
    This deliberately eliminates the non-XLS PURCHASING/IMPORTED placeholder.
    """
    value = f" {normalize(name)} "
    for subgroup_code, terms in KEYWORDS.items():
        if any(term.strip().upper() in value for term in terms):
            return ITEM_CLASSES[subgroup_code]
    return ITEM_CLASSES["1-8"]


def allocate_code(item_class: ItemClass, occupied: set[str]) -> str:
    group, subgroup = item_class.subgroup_code.split("-", 1)
    code_prefix = f"{group}-{subgroup}"
    pattern = re.compile(rf"^{re.escape(code_prefix)}(\d{{5}})$")
    maximum = 0
    for raw in occupied:
        match = pattern.fullmatch(str(raw or "").upper())
        if match:
            maximum = max(maximum, int(match.group(1)))
    for sequence in range(maximum + 1, 100000):
        candidate = f"{code_prefix}{sequence:05d}"
        if candidate.upper() not in occupied:
            occupied.add(candidate.upper())
            return candidate
    raise RuntimeError(f"Item code range exhausted for subgroup {item_class.subgroup_code}")
