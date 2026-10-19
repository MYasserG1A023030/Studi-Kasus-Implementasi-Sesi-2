# Menjalankan Studi Kasus di HPC (SLURM)

Dokumen ini menerjemahkan alur kerja HPC yang dijelaskan dalam webinar
"Bridging Global Infrastructure to Address Local Challenges in HPC" menjadi
perintah konkret untuk repo ini.

## Alur yang dipakai (sesuai webinar)

| Langkah webinar | Perintah nyata |
|---|---|
| Membuat akun di pusat superkomputer | Registrasi di portal HPC (permintaan akses + persetujuan) |
| Membuat pasangan kunci SSH | `ssh-keygen -t ed25519 -C "nama@email"` |
| Mendaftarkan public key | `ssh-copy-id -i ~/.ssh/id_ed25519.pub user@cluster` atau tempel ke portal |
| Masuk ke cluster | `ssh user@cluster` (semua superkomputer berbasis Linux) |
| Menulis batch script | `hpc/job.slurm` |
| Mengirim job | `sbatch --array=1-100 hpc/job.slurm` |
| Memantau job | `squeue -u $USER`, `sacct -j <jobid> --format=JobID,State,Elapsed,MaxRSS` |
| Mengunduh hasil | `scp user@cluster:~/simulasi-kebijakan-listrik/results/sweep_results.csv results/` |
| Menganalisis di komputer sendiri | `python src/analysis.py` |

## Dua pola paralel yang dipakai

### 1. Array job (disarankan) - `hpc/job.slurm`

Satu elemen array = satu kebijakan yang disimulasikan. Karena setiap
simulasi saling bebas (*embarrassingly parallel*), tiap task bisa berjalan di
node berbeda tanpa komunikasi.

```bash
mkdir -p logs results/slurm
sbatch --array=1-100 hpc/job.slurm
```

Array job memetakan 1 task SLURM = 1 kebijakan. Skrip membaca
`data/policies.csv` baris ke-$((SLURM_ARRAY_TASK_ID + 1)) lalu memanggil
`src/sweep_serial.py --policy-id ...` sehingga tiap task menulis CSV sendiri
ke `results/slurm/<POLICY_ID>.csv`.

Setelah semua task selesai, gabungkan hasilnya:

```bash
python src/merge_results.py --input results/slurm --out results/sweep_results.csv
python src/analysis.py
```

### 2. Satu node banyak core - `hpc/job_single_node.slurm`

Setara dengan `src/sweep_parallel.py` di laptop: satu job, satu node, N core
dipakai sebagai N proses python. Mudah, tapi tidak bisa melewati batas satu
node.

```bash
sbatch hpc/job_single_node.slurm
```

## Ukuran pekerjaan

| Perintah | Simulasi | Perkiraan waktu di 1 core |
|---|---|---|
| `python src/sweep_serial.py --reps 30` | 3.030 | ~14 detik |
| `python src/sweep_parallel.py --workers 16 --reps 30` | 3.030 | ~4 detik |
| `python src/benchmark.py --reps 60` | 6.000 per titik skala | ~45 detik per titik |

Di cluster, ukuran yang wajar adalah menaikkan `--reps` (misalnya 200-1000)
atau memperluas grid kebijakan di `data/policies.csv`. Karena setiap simulasi
hanya butuh sekitar 7 ms, satu core SLURM dapat menyelesaikan ribuan simulasi
kebijakan per jam - jauh di bawah ambang biaya alokasi core-jam yang biasanya
dipakai pusat HPC.

## Catatan etika dan reproducibility

1. **Seed tunggal untuk semua task.** Semua simulasi diturunkan dari `SEED`
   yang sama dan `policy_id` yang berbeda, sehingga hasilnya dapat direproduksi
   siapa pun dari repo ini, di mesin mana pun.
2. **Jangan menabrak kuota komputasi.** Jalankan benchmark skala besar pada
   periode di luar jam sibuk, dan gunakan `--reps` secukupnya.
3. **Data sintetis, bukan data pribadi.** Folder `data/` berisi asumsi, bukan
   data nyata kampus. Kalau diganti dengan jadwal nyata, buang kolom yang
   memuat identitas mahasiswa.
4. **Unduh hasil, bukan setiap file.** Ambil `results/sweep_results.csv`
   (sekitar 1-2 MB) dan analisis di laptop.
