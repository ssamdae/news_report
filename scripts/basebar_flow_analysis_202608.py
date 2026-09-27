"""Join August base bars with reclaim outcomes and summarize D0 investor flow.

Rates use only resolved first-reclaim outcomes. Pending observations remain visible.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path


BASE = Path("output/basebar_202608_test.csv")
PATH = Path("output/basebar_202608_reclaim.csv")
OUTPUT = Path("output/basebar_202608_flow_joined.csv")
RESOLVED = {"settled", "failed_first_reclaim"}
PENDING = {"no_pullback_yet", "no_reclaim_yet", "awaiting_settlement"}
OTHER = {"no_pullback_within_horizon", "no_reclaim_within_horizon", "base_close_mismatch"}


def read_csv(path: Path, date_column: str) -> dict[tuple[str, str], dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"Empty CSV: {path}")
    if not {"stock_code", date_column}.issubset(rows[0]):
        raise ValueError(f"Missing ticker/date columns in {path}")
    keyed = {(row["stock_code"], row[date_column]): row for row in rows}
    if len(keyed) != len(rows):
        raise ValueError(f"Duplicate ticker/date in {path}")
    return keyed


def sign(value: Decimal) -> str:
    return "+" if value > 0 else "-" if value < 0 else "0"


def foreign_band(value: Decimal) -> str:
    if value < -10:
        return "<-10%"
    if value < 0:
        return "-10%~0%"
    if value < 10:
        return "0%~10%"
    return ">=10%"


def join(base: dict, paths: dict) -> list[dict]:
    if base.keys() != paths.keys():
        raise ValueError(f"Unmatched keys: base_only={len(base.keys()-paths.keys())}, "
                         f"path_only={len(paths.keys()-base.keys())}")
    joined = []
    for key in sorted(base, key=lambda key: (key[1], key[0])):
        bar, path = base[key], paths[key]
        if bar.get("investor_flow_status") != "ok":
            raise ValueError(f"Investor flow not complete: {key}")
        status = path["status"]
        if status not in RESOLVED | PENDING | OTHER:
            raise ValueError(f"Unknown path status: {key} {status}")
        value = Decimal(bar["trade_value"])
        if value <= 0:
            raise ValueError(f"Nonpositive trading value: {key}")
        for name in ("individual", "foreign", "institution"):
            net = Decimal(bar[f"{name}_net"])
            ratio = Decimal(bar[f"{name}_net_ratio"])
            if abs(ratio - net / value * 100) > Decimal("0.0001"):
                raise ValueError(f"Investor ratio mismatch: {key} {name}")
        joined.append({**bar, **{f"path_{column}": content for column, content in path.items()}})
    return joined


def summarize(rows: list[dict], label: str, group_by) -> None:
    groups: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        groups[group_by(row)][row["path_status"]] += 1
    print(f"\n[{label}] group | total | settled | failed_first_reclaim | pending | settled/resolved")
    for group in sorted(groups):
        counts = groups[group]
        resolved = sum(counts[status] for status in RESOLVED)
        pending = sum(counts[status] for status in PENDING)
        total = sum(counts.values())
        rate = f"{counts['settled'] / resolved * 100:.1f}%" if resolved else "n/a"
        print(f"{group} | {total} | {counts['settled']} | "
              f"{counts['failed_first_reclaim']} | {pending} | {rate}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=BASE)
    parser.add_argument("--path", type=Path, default=PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    rows = join(read_csv(args.base, "trade_date"), read_csv(args.path, "signal_date"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summarize(rows, "foreign net ratio", lambda row: foreign_band(Decimal(row["foreign_net_ratio"])))
    summarize(rows, "foreign / individual signs", lambda row:
              f"foreign{sign(Decimal(row['foreign_net']))} / "
              f"individual{sign(Decimal(row['individual_net']))}")
    summarize(rows, "institution sign", lambda row:
              f"institution{sign(Decimal(row['institution_net']))}")
    print(f"\n[DONE] joined={len(rows)}, output={args.output}")
    print("Rates exclude pending observations; groups with small resolved counts are exploratory.")


if __name__ == "__main__":
    main()
