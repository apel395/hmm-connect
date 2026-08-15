#!/usr/bin/env python3
"""Compatibility runner for the Purchasing Item Master seed.

The historical workbook extraction contains 1,425 raw item labels, but the Item
Master seed intentionally matches products using the same normalized name key
used by the application import logic. After normalization, spelling/punctuation/
spacing variants collapse to 1,311 unique Item Master candidates.

Business rule:
- Fresh vegetables / vegetable items are always seeded as EXEMPT (Non-PPN).

This runner patches the validation guard and tax classification, then delegates
database work, dry-run/apply behavior, deterministic product codes, and
idempotency to seed_purchasing_item_master.py.
"""

from __future__ import annotations

import base64
import json
import re
import zlib

import scripts.seed_purchasing_item_master as seed

EXPECTED_RAW_LABELS = 1425
EXPECTED_NORMALIZED_ITEMS = 1311

# HMM business rule: vegetables are Non-PPN. Keep this explicit and conservative
# so unrelated prepared/processed products are not accidentally classified exempt.
VEGETABLE_TERMS = {
    "bayam", "kangkung", "sawi", "pakcoy", "pak choi", "bok choy",
    "wortel", "kol", "kubis", "buncis", "kacang panjang", "tauge", "toge",
    "timun", "ketimun", "mentimun", "terong", "labu", "oyong", "gambas",
    "pare", "brokoli", "kembang kol", "cauliflower", "selada", "lettuce",
    "seledri", "celery", "daun singkong", "daun pepaya", "daun ubi",
    "daun katuk", "daun kelor", "daun bawang", "daun sop", "daun salam",
    "daun jeruk", "kemangi", "genjer", "kenikir", "rebung", "jagung muda",
    "baby corn", "lobak", "radish", "bit", "beet", "paprika", "tomat",
    "tomato", "kapri", "kailan", "chaisim", "caisim", "petsai", "pecay",
    "pucuk labu", "jantung pisang", "nangka muda", "melinjo",
}


def _is_vegetable(name: str) -> bool:
    value = re.sub(r"[^a-z0-9]+", " ", name.casefold()).strip()
    padded = f" {value} "
    return any(f" {term} " in padded for term in VEGETABLE_TERMS)


def load_rows_normalized() -> list[dict]:
    high_mapping = json.loads(
        zlib.decompress(base64.b64decode(seed.MAPPING_B64)).decode("utf-8")
    )
    rows = [
        {
            "Item": name,
            "Proposed Tax Category": category,
            "Confidence": "HIGH",
            "Reason": "High-confidence classification from historical Purchasing tax mapping",
        }
        for name, category in high_mapping.items()
    ]
    remainder = json.loads(
        zlib.decompress(
            base64.b85decode(seed.REMAINDER_B85.encode("ascii"))
        ).decode("utf-8")
    )
    rows.extend(remainder)

    if len(rows) != EXPECTED_RAW_LABELS:
        raise RuntimeError(
            "Embedded Purchasing payload is incomplete: "
            f"expected {EXPECTED_RAW_LABELS} raw labels, got {len(rows)}"
        )

    by_key: dict[str, dict] = {}
    for row in rows:
        key = seed.normalized(str(row.get("Item") or ""))
        if key and key not in by_key:
            by_key[key] = dict(row)

    result = list(by_key.values())
    if len(result) != EXPECTED_NORMALIZED_ITEMS:
        raise RuntimeError(
            "Embedded Purchasing normalized payload changed unexpectedly: "
            f"expected {EXPECTED_NORMALIZED_ITEMS} Item Master candidates, got {len(result)}"
        )

    vegetable_count = 0
    for row in result:
        name = str(row.get("Item") or "")
        if not _is_vegetable(name):
            continue
        row["Proposed Tax Category"] = "EXEMPT"
        row["Confidence"] = "HIGH"
        row["Reason"] = "HMM business rule: vegetable items are Non-PPN"
        vegetable_count += 1

    print(f"Vegetable Non-PPN override candidates: {vegetable_count}")
    return result


seed.load_rows = load_rows_normalized


if __name__ == "__main__":
    raise SystemExit(seed.main())
