#!/usr/bin/env python3
"""Compatibility runner for the Purchasing Item Master seed.

The historical workbook extraction contains 1,425 raw item labels, but the Item
Master seed intentionally matches products using the same normalized name key
used by the application import logic. After normalization, spelling/punctuation/
spacing variants collapse to 1,311 unique Item Master candidates.

This runner patches only that validation guard and delegates all database work,
dry-run/apply behavior, tax classification, deterministic product codes, and
idempotency to seed_purchasing_item_master.py.
"""

from __future__ import annotations

import base64
import json
import zlib

import scripts.seed_purchasing_item_master as seed

EXPECTED_RAW_LABELS = 1425
EXPECTED_NORMALIZED_ITEMS = 1311


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

    # The source extraction has 1,425 raw labels. Item Master uses normalized
    # names for identity, so equivalent labels are deliberately collapsed.
    if len(rows) != EXPECTED_RAW_LABELS:
        raise RuntimeError(
            "Embedded Purchasing payload is incomplete: "
            f"expected {EXPECTED_RAW_LABELS} raw labels, got {len(rows)}"
        )

    by_key: dict[str, dict] = {}
    for row in rows:
        key = seed.normalized(str(row.get("Item") or ""))
        if key and key not in by_key:
            by_key[key] = row

    result = list(by_key.values())
    if len(result) != EXPECTED_NORMALIZED_ITEMS:
        raise RuntimeError(
            "Embedded Purchasing normalized payload changed unexpectedly: "
            f"expected {EXPECTED_NORMALIZED_ITEMS} Item Master candidates, got {len(result)}"
        )
    return result


seed.load_rows = load_rows_normalized


if __name__ == "__main__":
    raise SystemExit(seed.main())
