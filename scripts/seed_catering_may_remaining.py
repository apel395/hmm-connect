"""Seed the remaining May Catering drafts while retaining verified existing journals."""
import argparse
from functools import partial
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.request import urlopen

from catering_may_existing_coverage import EXPECTED, verify_database
from seed_catering_january_journals import URL, run_db
from seed_catering_may_journals import END, PREFIX, START, TAB, prepare_month


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xlsx", type=Path)
    parser.add_argument("--source-only", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-plan")
    args = parser.parse_args()
    if args.source_only and args.apply:
        parser.error("--source-only and --apply are mutually exclusive")
    if args.xlsx is None:
        with TemporaryDirectory(prefix="catering-may-") as directory:
            workbook = Path(directory) / "kas-harian.xlsx"
            with urlopen(URL, timeout=60) as response:
                workbook.write_bytes(response.read())
            source, drafts, control, report = prepare_month(workbook)
    else:
        source, drafts, control, report = prepare_month(args.xlsx)
    if not report["source_controls_pass"]:
        print(json.dumps(report, default=str, indent=2))
        parser.error("Source controls failed")
    if len(drafts) != 956 or not set(EXPECTED).issubset({row[0] for row in drafts}):
        parser.error("Source coverage changed")
    remaining = [row for row in drafts if row[0] not in EXPECTED]
    report["source_journals"] = report["drafts"]
    report["drafts"] = len(remaining)
    report["existing_journals_to_verify"] = len(EXPECTED)
    print(json.dumps(report, default=str, indent=2))
    if not args.source_only:
        run_db(
            args, remaining, control, source, start=START, end=END, tab=TAB, prefix=PREFIX,
            fees={}, splits={}, location_overrides={}, supporting_details={},
            existing_coverage=partial(
                verify_database, drafts=drafts, remaining=remaining, control=control,
            ),
        )


if __name__ == "__main__":
    main()
