#!/bin/bash
#SBATCH --job-name=simulasi-kebijakan
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:30:00
#SBATCH --output=logs/slurm-%A_%a.out
#SBATCH --error=logs/slurm-%A_%a.err
#SBATCH --array=1-100

# ------------------------------------------------------------------
# SLURM array job: satu elemen array = satu kebijakan yang disimulasikan.
#
# Ini pemetaan paling natural untuk pekerjaan yang "embarrassingly parallel":
# tiap kebijakan saling bebas, jadi tiap task bisa berjalan di node berbeda
# tanpa perlu komunikasi antar proses.
#
# Pakai:
#   mkdir -p logs results/slurm
#   sbatch --array=1-100 hpc/job.slurm
#   squeue -u $USER
#   sacct -j <jobid> --format=JobID,State,Elapsed,MaxRSS
#   python src/merge_results.py --input results/slurm --out results/sweep_results.csv
# ------------------------------------------------------------------

set -euo pipefail

# 1. Akun dan kunci SSH sudah disiapkan sebelum masuk ke cluster.
#    Kunci publik didaftarkan sekali: ssh-copy-id -i ~/.ssh/id_ed25519.pub user@cluster
# 2. Nama modul Python berbeda antar cluster; sesuaikan bila perlu.
module load python/3.11 || true

# 3. Lingkungan virtual (opsional, tapi HPC biasanya butuh versi tetap).
if [ -f "$HOME/venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source "$HOME/venv/bin/activate"
fi

PROJECT_DIR="${PROJECT_DIR:-$HOME/simulasi-kebijakan-listrik}"
cd "$PROJECT_DIR" || exit 1

mkdir -p logs results/slurm

# 4. Petition policy mana yang dihitung oleh task ini.
#    policies.csv punya baris header, jadi kebijakan ke-N ada di baris N+1.
#    Dengan sbatch --array=1-100, SLURM_ARRAY_TASK_ID berjalan 1..100.
#    (Kebijakan status quo "BASE" adalah baris 101, jalankan terpisah bila perlu.)
POLICY_ID=$(sed -n "$((SLURM_ARRAY_TASK_ID + 1))p" data/policies.csv | cut -d, -f1)

REPS="${REPS:-30}"
SEED="${SEED:-20260101}"
OUT="results/slurm/${POLICY_ID}.csv"

echo "[$(date -u +%FT%TZ)] task ${SLURM_ARRAY_TASK_ID} (${SLURM_JOB_ID}) mulai"
echo "[$(date -u +%FT%TZ)] host=$(hostname) kebijakan=${POLICY_ID} reps=${REPS}"

python src/sweep_serial.py \
  --policy-id "${POLICY_ID}" \
  --reps "${REPS}" \
  --seed "${SEED}" \
  --data-dir data \
  --out "${OUT}"

echo "[$(date -u +%FT%TZ)] task ${SLURM_ARRAY_TASK_ID} selesai -> ${OUT}"
