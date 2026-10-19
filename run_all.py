"""Menjalankan seluruh pipeline studi kasus dari awal sampai akhir.

Jalankan dengan: python run_all.py
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYTHON = sys.executable

TAHAP = [
    ("Generator data sintetis", ["src/make_data.py"]),
    ("Uji kebenaran model", ["tests/test_model.py"]),
    ("Sweep kebijakan paralel",
     ["src/sweep_parallel.py", "--workers", "{workers}", "--reps", "{reps}",
      "--out", "results/sweep_results.csv", "--timing-out", "results/timing_last.json"]),
    ("Benchmark paralel dan Amdahl", ["src/benchmark.py", "--reps", "{bench_reps}"]),
    ("Analisis dan rekomendasi", ["src/analysis.py"]),
]


def log(label: str, pesan: str) -> None:
    print(f"[{label}] {pesan}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Menjalankan seluruh pipeline studi kasus.")
    parser.add_argument("--workers", type=int, default=8,
                        help="jumlah proses pekerja untuk sweep (default: 8)")
    parser.add_argument("--reps", type=int, default=30,
                        help="pengulangan acak per kebijakan (default: 30)")
    parser.add_argument("--bench-reps", type=int, default=60,
                        help="pengulangan acak per titik benchmark (default: 60)")
    parser.add_argument("--skip-benchmark", action="store_true",
                        help="lewati tahap benchmark (pipeline jadi ~20 detik)")
    args = parser.parse_args()

    placeholder = {
        "workers": str(args.workers),
        "reps": str(args.reps),
        "bench_reps": str(args.bench_reps),
    }

    tahap = [t for t in TAHAP if not (args.skip_benchmark and "Benchmark" in t[0])]

    mulai = time.time()
    log("run_all", f"memulai {len(tahap)} tahap")
    durasi: list[tuple[str, float]] = []
    for nama, perintah in tahap:
        waktu = time.time()
        log("run_all", f"--- {nama} ---")
        perintah_final = [arg.format(**placeholder) for arg in perintah]
        hasil = subprocess.run([PYTHON, *perintah_final], cwd=ROOT, check=False)
        if hasil.returncode != 0:
            log("run_all", f"GAGAL di tahap: {nama}")
            return hasil.returncode
        durasi.append((nama, time.time() - waktu))

    log("run_all", "ringkasan waktu tahap:")
    for nama, detik in durasi:
        print(f"    {nama:<38} {detik:7.1f} detik")
    log("run_all", f"selesai total {time.time() - mulai:.1f} detik")
    log("run_all", "ringkasan kebijakan: results/recommended_policy.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
