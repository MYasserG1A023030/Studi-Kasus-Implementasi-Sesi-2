"""Sweep kebijakan secara paralel: multiprocessing atau joblib.

Tugas sweep bersifat *embarrassingly parallel*: setiap kombinasi
(kebijakan, pengulangan acak) adalah simulasi yang sepenuhnya independen.
Tidak ada state bersama antar simulasi, jadi cukup memecah pekerjaan ke
pekerja terpisah.

Jalankan::

    python src/sweep_parallel.py --workers 8 --reps 30
    python src/sweep_parallel.py --workers 8 --backend joblib

Di Windows, ``multiprocessing`` memakai metode ``spawn``: modul utama diimpor
ulang oleh setiap proses anak, sehingga seluruh pekerjaan utama wajib berada
di dalam guard ``if __name__ == "__main__":``.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import model  # noqa: E402

_WORKER_STATE: dict = {}


def _init_worker(data_dir: str, seed: int) -> None:
    """Muat gedung sekali saja per proses pekerja (hemat parsing CSV)."""
    _WORKER_STATE["building"] = model.load_building(Path(data_dir))
    _WORKER_STATE["seed"] = seed


def _run_chunk(task: tuple[model.Policy, int, int]) -> list[model.SimResult]:
    """Jalankan satu pecahan pekerjaan: kebijakan + rentang pengulangan."""
    policy, rep_start, rep_end = task
    building = _WORKER_STATE["building"]
    seed = _WORKER_STATE["seed"]
    return model.simulate_chunk(policy, building, seed, rep_start, rep_end)


def _run_chunk_joblib(
    task: tuple[model.Policy, int, int, model.Building, int],
) -> list[model.SimResult]:
    """Varian joblib: gedung ikut dikirim sebagai argumen (loky mem-pickle)."""
    policy, rep_start, rep_end, building, seed = task
    return model.simulate_chunk(policy, building, seed, rep_start, rep_end)


def build_tasks(
    policies: list[model.Policy],
    reps: int,
    reps_per_task: int,
) -> list[tuple[model.Policy, int, int]]:
    """Pecah sweep menjadi unit kerja kecil namun cukup kasar agar IPC tidak dominan."""
    tasks: list[tuple[model.Policy, int, int]] = []
    for policy in policies:
        start = 0
        while start < reps:
            end = min(start + reps_per_task, reps)
            tasks.append((policy, start, end))
            start = end
    return tasks


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sweep kebijakan paralel.")
    parser.add_argument("--workers", type=int, default=8, help="jumlah proses pekerja")
    parser.add_argument("--reps", type=int, default=30, help="pengulangan acak per kebijakan")
    parser.add_argument("--seed", type=int, default=20260101)
    parser.add_argument("--backend", choices=["multiprocessing", "joblib"],
                        default="multiprocessing")
    parser.add_argument("--reps-per-task", type=int, default=0,
                        help="besar pecahan kerja (0 = otomatis)")
    parser.add_argument("--data-dir", type=Path, default=model.DATA_DIR)
    parser.add_argument("--out", type=Path,
                        default=model.RESULTS_DIR / "sweep_results.csv")
    parser.add_argument("--timing-out", type=Path,
                        default=model.RESULTS_DIR / "timing_last.json")
    parser.add_argument("--exclude-baseline", dest="include_baseline",
                        action="store_false", default=True)
    return parser.parse_args()


def run_parallel(
    policies: list[model.Policy],
    bld: model.Building,
    seed: int,
    reps: int,
    workers: int,
    backend: str = "multiprocessing",
    reps_per_task: int = 0,
    data_dir: Path = model.DATA_DIR,
) -> tuple[list[model.SimResult], float]:
    """Jalankan sweep paralel dan kembalikan (hasil, waktu dinding).

    Fungsi ini dipakai oleh CLI maupun ``benchmark.py`` agar pengukuran
    kecepatan memakai jalur kode yang sama persis.
    """
    reps_per_task = reps_per_task or max(1, reps // 4)
    tasks = build_tasks(policies, reps, reps_per_task)

    if workers <= 1:
        start = time.perf_counter()
        results = [
            res
            for policy, rep_start, rep_end in tasks
            for res in model.simulate_chunk(policy, bld, seed, rep_start, rep_end)
        ]
        return results, time.perf_counter() - start

    if backend == "joblib":
        from joblib import Parallel, delayed

        payload = [(p, s, e, bld, seed) for p, s, e in tasks]
        start = time.perf_counter()
        chunks = Parallel(n_jobs=workers, backend="loky")(
            delayed(_run_chunk_joblib)(task) for task in payload
        )
        elapsed = time.perf_counter() - start
        return [res for chunk in chunks for res in chunk], elapsed

    start = time.perf_counter()
    with ProcessPoolExecutor(
        max_workers=workers,
        initializer=_init_worker,
        initargs=(str(data_dir), seed),
    ) as pool:
        chunks = list(pool.map(_run_chunk, tasks, chunksize=max(1, len(tasks) // (workers * 8))))
    elapsed = time.perf_counter() - start
    return [res for chunk in chunks for res in chunk], elapsed


def main() -> int:
    args = parse_args()
    bld = model.load_building(args.data_dir)
    policies = model.load_policies(args.data_dir)
    if not args.include_baseline:
        policies = [p for p in policies if not p.is_baseline]

    total = len(policies) * args.reps
    reps_per_task = args.reps_per_task or max(1, args.reps // 4)
    tasks = build_tasks(policies, args.reps, reps_per_task)

    print(f"[paralel] backend={args.backend} pekerja={args.workers} "
          f"tugas={len(tasks)} (total {total} simulasi)")

    results, elapsed = run_parallel(
        policies=policies,
        bld=bld,
        seed=args.seed,
        reps=args.reps,
        workers=args.workers,
        backend=args.backend,
        reps_per_task=reps_per_task,
        data_dir=args.data_dir,
    )

    model.write_results_csv(args.out, results, {p.policy_id: p for p in policies})
    payload = {
        "backend": args.backend,
        "workers": args.workers,
        "reps": args.reps,
        "n_simulations": len(results),
        "n_tasks": len(tasks),
        "wall_time_s": elapsed,
        "simulations_per_s": len(results) / elapsed,
    }
    args.timing_out.parent.mkdir(parents=True, exist_ok=True)
    args.timing_out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"[paralel] selesai dalam {elapsed:.3f} detik "
          f"({len(results) / elapsed:.1f} simulasi/detik)")
    print(f"[paralel] hasil ditulis ke {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
