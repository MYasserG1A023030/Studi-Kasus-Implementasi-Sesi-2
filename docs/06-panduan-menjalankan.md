# 6. Panduan Menjalankan dan Mengembangkan

## 6.1 Persiapan

```bash
cd Studi-Kasus-Implementasi-Sesi-2
python -m pip install -r requirements.txt
```

Versi yang dipakai saat dokumentasi ini ditulis: Python 3.11, numpy 2.4,
pandas 2.3, matplotlib 3.11, joblib 1.6.

## 6.2 Menjalankan seluruh pipeline

```bash
python run_all.py
```

Pipeline berjalan berurutan: generator data sintetis -> uji kebenaran model ->
sweep kebijakan paralel -> benchmark paralel dan Amdahl -> analisis dan
rekomendasi. Seluruhnya sekitar 2,5 menit di laptop biasa; tahap benchmark
menyumbang sekitar 2 menit di dalamnya.

Menjalankan lebih cepat dengan melewati benchmark:

```bash
python run_all.py --skip-benchmark
```

Menjalankan satu tahap saja:

```bash
python src/make_data.py
python tests/test_model.py
python src/sweep_serial.py --reps 30
python src/sweep_parallel.py --workers 8 --reps 30
python src/benchmark.py --reps 60
python src/analysis.py
```

## 6.3 Keluaran yang dihasilkan

| Folder | Isi |
|---|---|
| `data/` | 4 berkas CSV: inventaris ruang, jadwal, cuaca, grid kebijakan |
| `results/sweep_results.csv` | 3.030 baris, satu per (kebijakan, pengulangan) |
| `results/policy_summary.csv` | Ringkasan per kebijakan: energi, ketidaknyamanan, pelanggaran, hemat, kelayakan |
| `results/recommended_policy.json` | Kebijakan yang direkomendasikan beserta alasannya |
| `results/timings.csv`, `results/speedup.csv` | Waktu serial versus paralel, speedup, efisiensi, parameter Amdahl |
| `results/crossover.csv` | Titik impas serial versus paralel |
| `results/hardware_ceiling.csv` | Batas scaling mesin lokal dari beban CPU murni |
| `results/figures/` | 4 grafik: profil beban, frontier kebijakan, peta panas, kurva speedup |
| `results/benchmark_log.txt` | Catatan keluaran benchmark |

## 6.4 Opsi yang sering dipakai

| Opsi | Fungsi |
|---|---|
| `python src/sweep_parallel.py --workers 16 --backend joblib` | Backend joblib (loky) alih-alih multiprocessing |
| `python src/sweep_parallel.py --reps 300` | Sweep lebih besar, lebih dekat ke beban HPC |
| `python src/sweep_serial.py --policy-id P020` | Satu kebijakan saja, dipakai SLURM array job |
| `python src/analysis.py --max-discomfort 40` | Mengubah ambang ketidaknyamanan |
| `python src/merge_results.py --input results/slurm` | Menggabungkan hasil per-kebijakan dari cluster |
| `python src/benchmark.py --workers 1 2 4 8 16` | Menguji titik skala yang berbeda |

## 6.5 Mengganti data sintetis dengan data nyata

1. Salin `data/rooms.csv`, lalu sesuaikan kolom berikut: `area_m2`,
   `capacity`, `ac_kw`, `ac_units`, `setpoint_c`, `setpoint_mode`, `critical`.
   Kolom `setpoint_mode` bernilai `policy` (setpoint mengikuti kebijakan) atau
   `cap` (ruang punya syarat suhu sendiri yang lebih dingin).
2. Salin `data/schedules.csv` dengan skema yang sama: `room_id`, `day`
   (0 = Senin sampai 6 = Minggu), `start_hour`, `end_hour`,
   `occupancy_fraction`.
3. Jalankan ulang `python src/make_data.py` hanya bila ingin membuat ulang
   cuaca dan grid kebijakan; berkas `rooms.csv` dan `schedules.csv` yang
   Anda ganti sendiri tidak akan ditimpa.
4. Jalankan `python src/sweep_parallel.py --reps 30` lalu
   `python src/analysis.py`.
5. Periksa kembali asumsi di `docs/02-model-simulasi.md` bagian 2.6 dan
   kalibrasi ulang bila hasil terlihat tidak masuk akal.

## 6.6 Validasi

`python tests/test_model.py` menjalankan 10 uji yang juga jalan di pytest:

| Uji | Yang dijamin |
|---|---|
| `test_building_loads` | 13 ruang, 168 jam, ada ruang kritis |
| `test_determinism` | Seed sama menghasilkan hasil sama; seed berbeda menghasilkan hasil berbeda |
| `test_energy_accounting` | Energi = energi AC + beban dasar, toleransi 1e-9 |
| `test_serial_matches_parallel` | Hasil serial identik dengan paralel, bit per bit |
| `test_critical_room_constraint` | `ac_start_hour` 6 tidak ada paparan; 10 ada paparan |
| `test_setpoint_saves_energy` | Setpoint 26 memakai energi lebih kecil dari 22 |
| `test_lab_close_saves_energy` | Lab tutup jam 17 memakai energi lebih kecil dari lab buka jam 23 |
| `test_policy_effect_direction` | AC lebih lambat menyala hemat energi, tapi tidak nyaman |
| `test_amdahl` | `fit_amdahl` mengembalikan parameter f yang benar, galat di bawah 0,02 |
| `test_write_and_read_results` | CSV hasil bisa dibaca kembali utuh |

## 6.7 Menjalankan di cluster HPC

Lihat `hpc/README.md` untuk panduan lengkap: alur akun dan kunci SSH, SLURM
array job, penggabungan hasil, dan etika penggunaan kuota komputasi.
