"""Sweep kebijakan secara serial: baseline kecepatan dan sumber kebenaran hasil.

Jalankan::

    python src/sweep_serial.py --reps 30 --out results/sweep_results.csv
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import model  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sweep kebijakan serial (baseline HPC).")
    parser.add_argument("--reps", type=int, default=30,
                        help="jumlah pengulangan acak per kebijakan (default: 30)")
    parser.add_argument("--seed", type=int, default=20260101,
                        help="seed induk untuk seluruh simulasi")
    parser.add_argument("--data-dir", type=Path, default=model.DATA_DIR)
    parser.add_argument("--out", type=Path,
                        default=model.RESULTS_DIR / "sweep_results.csv")
    parser.add_argument("--policy-id", default="",
                        help="jalankan hanya kebijakan tertentu (pisah koma), "
                             "dipakai oleh SLURM array job")
    parser.add_argument("--include-baseline", action="store_true", default=True,
                        help="sertakan kebijakan status quo sebagai pembanding")
    parser.add_argument("--exclude-baseline", dest="include_baseline",
                        action="store_false")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    bld = model.load_building(args.data_dir)
    policies = model.load_policies(args.data_dir)
    if not args.include_baseline:
        policies = [p for p in policies if not p.is_baseline]
    if args.policy_id:
        wanted = {pid.strip() for pid in args.policy_id.split(",") if pid.strip()}
        policies = [p for p in policies if p.policy_id in wanted]
        if not policies:
            print(f"[serial] kebijakan {args.policy_id} tidak ditemukan di policies.csv")
            return 2

    total = len(policies) * args.reps
    print(f"[serial] {len(policies)} kebijakan x {args.reps} pengulangan = {total} simulasi")
    print(f"[serial] {bld.n_rooms} ruang, {bld.n_steps} jam (1 minggu), "
          f"langkah integrasi {model.ModelParams().dt_hours} jam")

    start = time.perf_counter()
    results = model.sweep_serial(policies, bld, args.seed, args.reps)
    elapsed = time.perf_counter() - start

    model.write_results_csv(args.out, results, {p.policy_id: p for p in policies})
    print(f"[serial] selesai dalam {elapsed:.3f} detik "
          f"({total / elapsed:.1f} simulasi/detik)")
    print(f"[serial] hasil ditulis ke {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
