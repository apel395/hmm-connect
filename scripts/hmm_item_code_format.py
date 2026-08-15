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


def allocate_code(item_class: ItemClass, occupied: set[str]) -> str:
    # XLS rule: subgroup 1-1 -> item 1-100001; subgroup 3-4 -> 3-400001.
    prefix = item_class.subgroup_code.replace("-", "-")
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
