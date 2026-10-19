"""Gabungkan hasil per-kebijakan (khasil SLURM array job) menjadi satu CSV.

Dipakai setelah job paralel selesai, baik di cluster maupun di laptop::

    python src/merge_results.py --input results/slurm --out results/sweep_results.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import model  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gabungkan CSV hasil per kebijakan.")
    parser.add_argument("--input", type=Path, default=model.RESULTS_DIR / "slurm",
                        help="folder berisi CSV per kebijakan")
    parser.add_argument("--out", type=Path,
                        default=model.RESULTS_DIR / "sweep_results.csv")
    return parser.parse_args()


REQUIRED_COLUMNS = {
    "policy_id", "rep", "energy_kwh", "energy_ac_kwh", "energy_base_kwh",
    "peak_kw", "discomfort_person_hours", "blocked_cooling_person_hours",
    "policy_violations", "critical_exposure_hours", "cost_idr",
}


def main() -> int:
    args = parse_args()
    files = sorted(Path(args.input).glob("*.csv"))
    if not files:
        print(f"[merge] tidak ada CSV di {args.input}")
        return 1

    rows: list[dict] = []
    fields: list[str] = []
    skipped: list[str] = []
    for path in files:
        with path.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            columns = set(reader.fieldnames or [])
            if not REQUIRED_COLUMNS.issubset(columns):
                skipped.append(path.name)
                continue
            if not fields:
                fields = list(reader.fieldnames or [])
            rows.extend(reader)

    if not rows:
        print(f"[merge] tidak ada CSV hasil sweep di {args.input} "
              f"(dilewati: {', '.join(skipped) or '-'})")
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    if skipped:
        print(f"[merge] dilewati (bukan hasil sweep): {', '.join(skipped)}")
    print(f"[merge] {len(files) - len(skipped)} file digabung -> {len(rows)} baris di {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
