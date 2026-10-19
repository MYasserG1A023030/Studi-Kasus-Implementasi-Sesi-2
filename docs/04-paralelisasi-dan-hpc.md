# 4. Paralelisasi dan HPC

## 4.1 Sifat pekerjaan

Setiap kombinasi (kebijakan, pengulangan acak) adalah simulasi yang berdiri
sendiri: tidak ada state bersama, tidak ada lock, tidak ada urutan yang harus
dihormati. Inilah bentuk *embarrassingly parallel* yang paling ideal - dan
pola yang sama dengan job HPC satu-kebijakan-per-task.

## 4.2 Hasil pengukuran

Diukur pada mesin lokal (Windows 11, 16 logical CPU, CPU terkuotasi), dengan
`python src/benchmark.py --reps 60` - 6.000 simulasi per titik skala:

| Pekerja | Waktu (detik) | Speedup | Efisiensi | Start up pool | Speedup steady-state |
|---|---|---|---|---|---|
| 1 (serial) | 27,22 | 1,00x | 100 % | - | - |
| 2 | 16,00 | 1,70x | 85,1 % | 0,21 s | 1,71x |
| 4 | 9,72 | 2,80x | 70,0 % | 0,21 s | 2,84x |
| 8 | 7,06 | 3,86x | 48,2 % | 0,21 s | 3,94x |
| 16 | 5,64 | 4,83x | 30,2 % | 0,24 s | 5,00x |

Regresi Hukum Amdahl pada data di atas menghasilkan **f = 0,846** dengan limit
speedup **6,49x**.

Sebagai pembanding, `results/hardware_ceiling.csv` menjalankan beban CPU murni
tanpa simulasi (start up pool dikurangkan): 1,69x pada 2 pekerja, 2,49x pada
4, 3,35x pada 8, dan 3,59x pada 16 pekerja. **Plafon mesin lokal inilah yang
membatasi scaling, bukan kode simulasi** - laptop atau VM ini hanya memberi
sekitar 4 core efektif meski melaporkan 16 logical CPU. Di node HPC
sungguhan dengan 64 core nyata, `f` akan mendekati 1 dan speedup bisa
mendekati linear sampai ke batas bandwidth memori.

## 4.3 Titik impas

Biaya start up pool di mesin ini 0,2 s, setara dengan sekitar 45 simulasi,
jadi paralel langsung menang sejak ukuran pekerjaan yang sangat kecil.

| Simulasi | Serial (detik) | Paralel 8 pekerja (detik) | Speedup |
|---|---|---|---|
| 700 | 3,40 | 1,26 | 2,71x |
| 1.400 | 6,56 | 2,04 | 3,22x |
| 2.800 | 13,08 | 3,45 | 3,79x |
| 5.600 | 25,34 | 6,35 | 3,99x |

Titik impas akan bergeser ke kanan begitu satu simulasi lebih mahal (misalnya
model yang dihitung berhari-hari) atau start up jauh lebih mahal (misalnya di
cluster dengan 60 detik untuk staging data dan menyalin modul). Inilah bentuk
paling sering dari Hukum Amdahl yang ditemui sehari-hari - termasuk di HPC,
di mana biaya *scheduling* job bisa melampaui biaya komputasinya sendiri.

## 4.4 Mengapa speedup tidak linear

Hukum Amdahl:

```
S(N) = 1 / ( (1 - f) + f/N )
```

karena pekerjaan tidak seluruhnya paralel: `f` adalah fraksi yang bisa
diparalelkan, dan `1 - f` adalah bagian serial.

Tiga penyebab nyata di repo ini:

1. **Start up proses.** Di Windows, `multiprocessing` memakai metode `spawn`:
   tiap pekerja adalah proses Python baru yang mengimpor ulang modul,
   termasuk numpy. Di sini biayanya kecil (0,2 s), tapi di cluster dengan
   staging data bisa jauh lebih besar.
2. **Beban I/O, bukan beban komputasi.** Semua pekerja membaca file CSV dan
   menulis hasil ke disk yang sama. Titik berat muncul saat bandwidth disk dan
   scheduler OS menjadi membatasi.
3. **Batas mesin, bukan batas kode.** Pengukuran `hardware_ceiling.csv`
   menjalankan beban CPU murni tanpa simulasi. Kalau plafon mesin hanya 3,6x,
   tidak ada algoritma yang bisa membuat speedup 16x.

Karena itu `src/benchmark.py` mengukur **dua** speedup: yang end-to-end
(termasuk start up) dan yang *steady-state* (start up pool dikurangi).
Selisihnya menunjukkan berapa besar bagian serialnya.

## 4.5 Menjalankan di cluster

Dua pola disediakan di folder `hpc/`:

| Berkas | Pola | Kapan dipakai |
|---|---|---|
| `hpc/job.slurm` | SLURM array job: satu elemen array = satu kebijakan | Skala besar lintas node |
| `hpc/job_single_node.slurm` | Satu node, banyak core | Setara `sweep_parallel.py` di laptop |

Penggabungan hasil per-kebijakan dilakukan `src/merge_results.py`:

```bash
python src/merge_results.py --input results/slurm --out results/sweep_results.csv
```

Perintah yang dipakai di cluster, sesuai urutan yang dijelaskan di webinar:

```bash
ssh-keygen -t ed25519                                   # 1. buat pasangan kunci
ssh-copy-id ~/.ssh/id_ed25519.pub user@cluster         # 2. daftarkan public key
ssh user@cluster                                        # 3. masuk ke cluster
sbatch --array=1-100 hpc/job.slurm                      # 4. kirim job
squeue -u $USER                                         # 5. pantau antrean
scp user@cluster:.../results/sweep_results.csv results/ # 6. unduh hasil
python src/analysis.py                                  # 7. analisis di komputer sendiri
```

Pemetaan dari materi webinar ke implementasi di repo ini:

| Pesan webinar | Wujud di repo ini |
|---|---|
| Bawa masalah lokal ke skala komputasi | Tagihan listrik gedung = masalah lokal, 3.030 simulasi = skala komputasi |
| Kodenya harus jalan di HPC | `hpc/job.slurm` (array job) dan `src/merge_results.py` |
| Integrator merancang alur dari masalah ke aplikasi | `data/` ke `src/model.py` ke `src/sweep_*.py` ke `src/analysis.py` ke `notebooks/` |
| Semua superkomputer pakai Linux | Skrip batch memakai bash, `module load`, `srun`, `sbatch` |
| Kompetisi HPC-AI dan sekolah HPC | Repo ini adalah bahan awal yang bisa langsung dibawa ke kompetisi |
| Tulis paper dengan artifact description | Semua asumsi, seed, dan perintah ada di README dan folder `docs/` |
