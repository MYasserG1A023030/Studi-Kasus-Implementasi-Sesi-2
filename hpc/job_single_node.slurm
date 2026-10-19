#!/bin/bash
#SBATCH --job-name=simulasi-listrik-1node
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=8G
#SBATCH --time=01:00:00
#SBATCH --output=logs/slurm-%j.out
#SBATCH --error=logs/slurm-%j.err

# ------------------------------------------------------------------
# Satu job SLURM, satu node, banyak core.
#
# Ini versi "satu proses python dengan banyak pekerja" yang setara dengan
# menjalankan src/sweep_parallel.py di laptop. Cocok untuk satu node dengan
# banyak core (misalnya node loginQUEUE atau node komputasi bersama).
#
# Untuk skala besar lintas node, pakai hpc/job.slurm (array job) yang
# distributes satu kebijakan per task.
# ------------------------------------------------------------------

set -euo pipefail

module load python/3.11 || true

if [ -f "$HOME/venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source "$HOME/venv/bin/activate"
fi

PROJECT_DIR="${PROJECT_DIR:-$HOME/simulasi-kebijakan-listrik}"
cd "$PROJECT_DIR" || exit 1

mkdir -p logs results

WORKERS="${WORKERS:-$SLURM_CPUS_PER_TASK}"
REPS="${REPS:-30}"
SEED="${SEED:-20260101}"

echo "[$(date -u +%FT%TZ)] host=$(hostname) pekerja=${WORKERS} reps=${REPS}"
srun --cpu-bind=cores python src/sweep_parallel.py \
  --workers "${WORKERS}" \
  --reps "${REPS}" \
  --seed "${SEED}" \
  --backend multiprocessing \
  --out results/sweep_results.csv \
  --timing-out results/timing_last.json

echo "[$(date -u +%FT%TZ)] selesai"
