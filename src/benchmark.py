"""Benchmark paralel: speedup, efisiensi, Hukum Amdahl, dan titik impas.

Eksperimen yang dijalankan:

1. *Scaling*  - sweep yang sama dijalankan dengan 1, 2, 4, 8, ... pekerja.
   Dihitung speedup = waktu serial / waktu paralel dan
   efisiensi = speedup / jumlah pekerja.
2. *Overhead* - biaya menjalankan kumpulan proses pekerja (start up pool,
   import numpy, shutdown) diukur terpisah agar bisa dipisahkan dari biaya
   komputasi murni.
3. *Impas*    - pada ukuran pekerjaan berapa paralel mulai lebih cepat
   daripada serial (titik crossover, illustrates Amdahl).
4. *Plafon mesin* - uji CPU murni tanpa simulasi, untuk melihat batas scaling
   perangkat keras lokal (bukan kode).

Jalankan::

    python src/benchmark.py --reps 150
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import model  # noqa: E402
import sweep_parallel as sp  # noqa: E402

RESULTS_DIR = model.RESULTS_DIR


def _burn(iterations: int) -> int:
    """Beban CPU murni untuk mengukur plafon scaling mesin."""
    total = 0
    for i in range(iterations):
        total += i * i
    return total


def _burn_chunk(args: tuple[int, int]) -> int:
    iterations, repeats = args
    total = 0
    for _ in range(repeats):
        total += _burn(iterations)
    return total


def measure_pool_startup(workers: int, repeats: int = 3) -> float:
    """Biaya membuat kumpulan proses pekerja (median dari beberapa percobaan)."""
    timings: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        with ProcessPoolExecutor(max_workers=workers) as pool:
            list(pool.map(_burn_chunk, [(1, 1)]))
        timings.append(time.perf_counter() - start)
    return statistics.median(timings)


def measure_hardware_ceiling(workers_list: list[int], work: int = 12_000_000) -> list[dict]:
    """Speedup maksimum yang bisa dicapai mesin ini untuk beban CPU murni.

    Beban sengaja dibuat besar (default ~1 detik per task) dan biaya start up
    pool dikurangkan, supaya yang terukur adalah batas paralelitas mesin, bukan
    biaya start up proses.
    """
    start = time.perf_counter()
    _burn(work)
    single = time.perf_counter() - start

    rows: list[dict] = []
    for workers in workers_list:
        startup = measure_pool_startup(workers, repeats=2)
        start = time.perf_counter()
        with ProcessPoolExecutor(max_workers=workers) as pool:
            list(pool.map(_burn_chunk, [(work, 1)] * workers))
        elapsed = time.perf_counter() - start
        corrected = max(elapsed - startup, 1e-6)
        speedup = (workers * single) / corrected
        rows.append({
            "workers": workers,
            "wall_time_s": elapsed,
            "pool_startup_s": startup,
            "corrected_time_s": corrected,
            "speedup": speedup,
            "efficiency": speedup / workers,
        })
    return rows


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark scaling paralel.")
    parser.add_argument("--reps", type=int, default=150,
                        help="pengulangan acak per kebijakan pada uji scaling")
    parser.add_argument("--seed", type=int, default=20260101)
    parser.add_argument("--workers", type=int, nargs="+",
                        default=[1, 2, 4, 8, 16],
                        help="daftar jumlah pekerja yang diuji")
    parser.add_argument("--skip-crossover", action="store_true")
    parser.add_argument("--skip-ceiling", action="store_true")
    parser.add_argument("--data-dir", type=Path, default=model.DATA_DIR)
    parser.add_argument("--out-dir", type=Path, default=RESULTS_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    bld = model.load_building(args.data_dir)
    policies = [p for p in model.load_policies(args.data_dir) if not p.is_baseline]
    n_sim = len(policies) * args.reps
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[benchmark] {len(policies)} kebijakan x {args.reps} rep = {n_sim} simulasi")

    serial_start = time.perf_counter()
    model.sweep_serial(policies, bld, args.seed, args.reps)
    serial_time = time.perf_counter() - serial_start
    print(f"[benchmark] serial: {serial_time:.3f} detik")

    timing_rows: list[dict] = [{
        "mode": "serial", "backend": "none", "workers": 1, "n_simulations": n_sim,
        "wall_time_s": serial_time, "simulations_per_s": n_sim / serial_time,
        "speedup": 1.0, "efficiency": 1.0, "pool_startup_s": 0.0,
    }]

    startup_cache: dict[int, float] = {}
    for workers in args.workers:
        if workers == 1:
            continue
        startup = measure_pool_startup(workers)
        startup_cache[workers] = startup
        _, elapsed = sp.run_parallel(
            policies=policies, bld=bld, seed=args.seed, reps=args.reps,
            workers=workers, backend="multiprocessing", data_dir=args.data_dir,
        )
        speedup = serial_time / elapsed
        steady = ((serial_time - startup) / (elapsed - startup)) if elapsed > startup else 0.0
        timing_rows.append({
            "mode": "parallel", "backend": "multiprocessing", "workers": workers,
            "n_simulations": n_sim, "wall_time_s": elapsed,
            "simulations_per_s": n_sim / elapsed, "speedup": speedup,
            "efficiency": speedup / workers, "pool_startup_s": startup,
        })
        print(f"[benchmark] {workers:2d} pekerja: {elapsed:7.3f} detik  "
              f"speedup={speedup:5.2f}x  efisiensi={speedup / workers * 100:5.1f}%  "
              f"(startup {startup:.3f} s, steady-state {steady:.2f}x)")

    write_csv(out_dir / "timings.csv", timing_rows, list(timing_rows[0].keys()))

    parallel_rows = [r for r in timing_rows if r["mode"] == "parallel"]
    worker_counts = [r["workers"] for r in parallel_rows]
    speedups = [r["speedup"] for r in parallel_rows]
    f_hat = model.fit_amdahl(speedups, worker_counts)
    print(f"[benchmark] Amdahl: fraksi paralel f = {f_hat:.3f} "
          f"(limit {1.0 / (1.0 - f_hat) if f_hat < 1 else float('inf'):.2f}x)")

    speedup_rows = []
    for row in parallel_rows:
        workers = row["workers"]
        speedup_rows.append({
            "workers": workers,
            "wall_time_s": row["wall_time_s"],
            "speedup": row["speedup"],
            "efficiency": row["efficiency"],
            "pool_startup_s": row["pool_startup_s"],
            "steady_state_speedup": (
                (serial_time - row["pool_startup_s"]) /
                (row["wall_time_s"] - row["pool_startup_s"])
                if row["wall_time_s"] > row["pool_startup_s"] else 0.0
            ),
            "amdahl_f": f_hat,
            "amdahl_predicted_speedup": model.amdahl_speedup(workers, f_hat),
            "amdahl_limit": (1.0 / (1.0 - f_hat)) if f_hat < 1.0 else float("inf"),
        })
    write_csv(out_dir / "speedup.csv", speedup_rows, list(speedup_rows[0].keys()))

    summary = {
        "n_simulations": n_sim,
        "serial_time_s": serial_time,
        "workers": worker_counts,
        "speedups": speedups,
        "amdahl_f": f_hat,
        "amdahl_limit": (1.0 / (1.0 - f_hat)) if f_hat < 1.0 else None,
        "pool_startup_s": startup_cache,
    }
    (out_dir / "benchmark_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")

    if not args.skip_crossover:
        print("[benchmark] titik impas serial vs paralel (8 pekerja):")
        crossover_rows = []
        for factor in (1, 2, 4, 8):
            reps = max(1, args.reps // 8 * factor)
            count = len(policies) * reps
            t0 = time.perf_counter()
            model.sweep_serial(policies, bld, args.seed, reps)
            t_serial = time.perf_counter() - t0
            _, t_par = sp.run_parallel(
                policies=policies, bld=bld, seed=args.seed, reps=reps,
                workers=8, backend="multiprocessing", data_dir=args.data_dir,
            )
            crossover_rows.append({
                "n_simulations": count, "reps": reps,
                "serial_time_s": t_serial, "parallel_time_s": t_par,
                "speedup": t_serial / t_par,
                "parallel_wins": int(t_par < t_serial),
            })
            print(f"    {count:6d} simulasi: serial {t_serial:6.3f} s vs "
                  f"paralel {t_par:6.3f} s  -> {'paralel menang' if t_par < t_serial else 'serial menang'}")
        write_csv(out_dir / "crossover.csv", crossover_rows, list(crossover_rows[0].keys()))

    if not args.skip_ceiling:
        print("[benchmark] plafon mesin (beban CPU murni, tanpa simulasi):")
        ceiling = measure_hardware_ceiling(args.workers)
        for row in ceiling:
            print(f"    {row['workers']:2d} pekerja: speedup {row['speedup']:5.2f}x")
        write_csv(out_dir / "hardware_ceiling.csv", ceiling, list(ceiling[0].keys()))

    print(f"[benchmark] keluaran ditulis ke {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
