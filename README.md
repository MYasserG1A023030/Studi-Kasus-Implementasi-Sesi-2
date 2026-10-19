# Simulasi Berbasis Agen untuk Kebijakan Penghematan Listrik Gedung Kampus

Studi kasus implementasi dari webinar **"Bridging Global Infrastructure to
Address Local Challenges in HPC"** (Informatics Practitioner Lecture Series
Universitas Bengkulu, narasumber Dr. Worawan Diaz Carballo, Thammasat University).

Ide yang diambil dari webinar: *"simulasi penghematan listrik gedung dengan
memodelkan perilaku manusia"*. Model fisik gedung saja tidak cukup, karena
tagihan listrik datang dari penggunanya. Repo ini mensimulasikan **perilaku
penghuni** di atas model termal gedung, lalu menguji kebijakan penghematan
sebelum diterapkan - dengan perhitungan yang sengaja dirancang untuk
dijalankan paralel di HPC.

| Isi repo | Keterangan |
|---|---|
| `src/` | Tujuh modul Python: simulator agen, pembuat data, sweep serial dan paralel, benchmark Amdahl, analisis kebijakan, penggabung hasil |
| `hpc/` | Dua batch script SLURM (array job per kebijakan, dan satu node banyak core) plus panduan alur kerja HPC sesuai webinar |
| `data/` | Data sintetis: inventaris 13 ruang, jadwal pemakaian, cuaca mingguan, dan grid 100 kebijakan |
| `results/` | 3.030 baris hasil simulasi, ringkasan 101 kebijakan, tabel waktu/speedup/impas, dan 4 grafik |
| `notebooks/` | Notebook analisis interaktif yang memuat ulang seluruh keluaran |
| `tests/` | 10 uji kebenaran: determinisme, kesetaraan serial-paralel, neraca energi, dan kepatuhan batasan ruang kritis |

---

## 1. Ringkasan Hasil

| Besaran | Status quo | Kebijakan rekomendasi | Selisih |
|---|---|---|---|
| Energi | 4.939,9 kWh/minggu | 3.886,4 kWh/minggu | **-21,3 %** |
| Biaya (Rp 1.500/kWh) | Rp 7.409.900/minggu | Rp 5.829.576/minggu | **-Rp 1.580.324/minggu** |
| Puncak beban | 124,8 kW | 120,1 kW | -3,8 % |
| Ketidaknyamanan | 22,7 orang-jam/minggu | 45,2 orang-jam/minggu | +22,5 |
| Pelanggaran manual (AC dinyalakan penghuni) | 0,0 / minggu | 5,0 / minggu | +5,0 |
| Paparan ruang kritis (Lab Biologi) | 0,0 jam | 0,0 jam | 0 |

Rekomendasi: **AC boleh menyala mulai jam 06:00, setpoint minimum gedung
26 °C, lab ditutup pukul 21:00** (`P020`).

Dari 101 kebijakan yang dievaluasi, 37 memenuhi dua batasan (tidak ada
paparan ruang kritis dan ketidaknyamanan di bawah ambang 60 orang-jam/minggu).
Kandidat dengan energi paling rendah (`P017`, hemat 22,0 %) ternyata memicu
2,4 kali lebih banyak peristiwa AC dinyalakan manual; `P020` hanya 0,9 % lebih
boros tetapi jauh lebih mudah ditegakkan - dan itu yang direkomendasikan.

### Temuan utama (dihitung otomatis oleh pipeline)

- **Setpoint adalah knob paling murah.** Menaikkan setpoint 22 → 25 °C
  menghemat **18,4 %** energi dengan tambahan ketidaknyamanan hanya 0,13 poin
  persen, dan tidak menyentuh batasan ruang kritis sama sekali.
- **"Jam mulai AC" adalah kunci yang berbahaya.** Menunda AC ke jam 09-10
  terlihat hemat 19-21 %, tetapi langsung menimbulkan **1.400-2.300 orang-jam**
  ketidaknyamanan dan **10-15 jam** ruang kritis tanpa pendinginan. Karena Lab
  Biologi mulai jam 07:00, semua kebijakan dengan `ac_start_hour >= 8`
  otomatis tidak layak.
- **Menutup lab terlalu cepat tidak memberi manfaat.** Menutup lab pukul
  18:00 hanya menghemat 0,5 % energi, tetapi memicu **2,5 kali** lebih banyak
  peristiwa AC dinyalakan manual. Kebijakan hemat yang tidak bisa ditegakkan
  berubah menjadi komplain dan biaya administrasi.
- **Energi termurah belum tentu kebijakan terbaik.** Kandidat `P017` (hemat
  22,0 %) memicu 2,4 kali lebih banyak pelanggaran manual dibanding `P020`
  (hemat 21,3 %); selisih energinya cuma 0,9 %.
- **Paralelisasi bekerja, tapi dibatasi mesin.** 6.000 simulasi: serial
  26,41 detik → 8 pekerja 6,99 detik (**3,78×**) → 16 pekerja 5,60 detik
  (**4,71×**). Regresi Amdahl memberi **f = 0,841** (limit 6,29×), sementara
  probe beban CPU murni menunjukkan plafon mesin lokal hanya **3,64×** - jadi
  saturasi berasal dari batas CPU laptop/VM, bukan dari kode.
- **Beban kerja baru masuk akal di HPC.** Satu simulasi hanya ~4,4 ms, jadi
  pekerjaan 3.030 simulasi bisa selesai di laptop dalam 4 detik; di HPC,
  gunanya adalah menjalankan *sweep* beribu pengulangan dan menulis paper
  dengan artifact description yang bisa diulang orang lain.

---

## 2. Masalah yang Dimodelkan

Gedung kampus dengan 13 ruang (5 kelas, 4 lab, 2 perpustakaan, ruang dosen,
ruang diskusi). Tiga knob kebijakan yang lazim dipakai manajemen gedung:

| Parameter | Arti | Rentang yang diuji |
|---|---|---|
| `ac_start_hour` | Jam paling awal AC boleh menyala di gedung | 6, 7, 8, 9, 10 |
| `min_setpoint_c` | Batas suhu minimum setpoint (AC tidak boleh mendinginkan di bawah ini) | 22, 23, 24, 25, 26 °C |
| `lab_close_hour` | Jam setelahnya AC lab harus dimatikan | 18, 19, 20, 21 |

Batasan nyata yang **tidak boleh dilanggar**:

* **Lab Biologi (ruang kritis)** - berisi freezer/inkubator, tidak boleh
  kehilangan pendinginan saat dipakai. Ruang ini dikecualikan dari aturan
  "jam tutup lab", tetapi tetap tunduk pada "jam mulai AC" gedung.
* **Ketidaknyamanan** - total orang-jam yang merasa terlalu panas atau terlalu
  dingin tidak boleh melewati ambang (default 60 orang-jam/minggu, sekitar
  0,45 % dari total jam-orang pemakaian).

Grid 5 × 5 × 4 = 100 kombinasi kebijakan × 30 pengulangan acak + 30 simulasi
kebijakan status quo = **3.030 simulasi**. Setiap kombinasi kebijakan dan
seed adalah simulasi yang sepenuhnya independen, sehingga pekerjaannya
*embarrassingly parallel*.

---

## 3. Struktur Repo

```
Studi-Kasus-Implementasi-Sesi-2/
├── README.md                  # dokumen ini
├── requirements.txt
├── src/
│   ├── model.py               # simulator: agen ruang, termal, kebijakan, metrik
│   ├── make_data.py           # pembuat data sintetis (rooms/schedules/weather/policies)
│   ├── sweep_serial.py        # sweep serial (baseline kecepatan + sumber kebenaran)
│   ├── sweep_parallel.py      # sweep paralel (multiprocessing / joblib)
│   ├── benchmark.py           # uji skala: speedup, efisiensi, Amdahl, titik impas
│   ├── analysis.py            # ringkasan kebijakan, rekomendasi, grafik
│   └── merge_results.py       # gabungkan CSV per-kebijakan (hasil SLURM array job)
├── hpc/
│   ├── job.slurm              # SLURM array job: 1 task = 1 kebijakan
│   ├── job_single_node.slurm  # 1 node, banyak core
│   └── README.md              # alur kerja HPC sesuai webinar
├── data/                      # data sintetis (dapat diganti data nyata)
│   ├── rooms.csv              # inventaris ruang
│   ├── schedules.csv          # jadwal pemakaian per hari
│   ├── weather.csv            # suhu udara luar per jam
│   └── policies.csv           # grid kebijakan + status quo
├── results/                   # keluaran (waktu, speedup, ringkasan kebijakan, grafik)
│   ├── sweep_results.csv      # 1 baris per (kebijakan, pengulangan)
│   ├── policy_summary.csv     # ringkasan per kebijakan
│   ├── recommended_policy.json
│   ├── timings.csv            # waktu serial vs paralel
│   ├── speedup.csv            # speedup, efisiensi, parameter Amdahl
│   ├── crossover.csv          # titik impas serial vs paralel
│   ├── hardware_ceiling.csv   # batas scaling mesin lokal
│   ├── benchmark_log.txt      # catatan keluaran benchmark
│   └── figures/               # 4 grafik hasil analisis
├── notebooks/analysis.ipynb   # analisis interaktif + grafik
└── tests/test_model.py        # 10 uji kebenaran (jalan tanpa pytest)
```

---

## 4. Cara Menjalankan

```bash
python -m venv .venv && . .venv/Scripts/activate      # Windows
pip install -r requirements.txt

python src/make_data.py                               # (opsional) buat ulang data sintetis
python tests/test_model.py                            # 10 uji kebenaran
python src/sweep_serial.py --reps 30                 # baseline serial (~14 detik)
python src/sweep_parallel.py --workers 8 --reps 30    # hasil utama (paralel, ~4 detik)
python src/benchmark.py --reps 60                     # uji skala + Amdahl (±4 menit)
python src/analysis.py                                # ringkasan + grafik
```

Di Linux/macOS, aktifkan venv dengan `source .venv/bin/activate`.

Semua perintah menerima `--help`. Perintah penting:

| Perintah | Fungsi |
|---|---|
| `python src/sweep_parallel.py --workers 16 --backend joblib` | Pakai backend joblib (loky) |
| `python src/sweep_parallel.py --reps 300` | Sweep lebih besar (lebih dekat ke beban HPC) |
| `python src/sweep_serial.py --policy-id P020` | Satu kebijakan saja (dipakai SLURM array job) |
| `python src/analysis.py --max-discomfort 40` | Ubah ambang ketidaknyamanan |
| `python src/merge_results.py --input results/slurm` | Gabungkan hasil dari cluster |

---

## 5. Model

### 5.1 Agen dan perilaku

Setiap ruang adalah satu agen yang menyimpan state internal: suhu udara, status
mesin AC, dan jumlah penghuni. Per jam, agen memutuskan:

1. **Berapa banyak penghuni?** Dari jadwal (+ ekor 1 jam untuk yang menuntaskan
   kerja, + lembur di lab pada malam hari), dikalikan derau acak 0,8-1,2.
2. **Apakah AC perlu dinyalakan?** Termostat: perlu bila suhu di atas
   setpoint. Selama beberapa waktu setelah ruang kosong, mesin menyelesaikan pendinginan
   (fase *hold*).
3. **Kalau kebijakan melarang AC menyala**, penghuni punya dua pilihan:
   menyalakan manual (peristiwa **pelanggaran kebijakan**) atau menahan diri
   (**ketidaknyamanan**). Peluangnya naik seiring bertambahnya penghuni di ruang.
4. **Pra-pendinginan** 1 jam sebelum jadwal dimulai (kebiasaan petugas),
   hanya bisa jalan bila kebijakan mengizinkan.

### 5.2 Termal

Model RC orde-1 per ruang (1 jam waktu simulasi, integrasi 15 menit):

```
T(t+1) = T(t) + dt * ( UA*(T_out - T) + Q_internal - Q_AC ) / C
```

* `UA` = 0,010 kW/K per m² (selubung gedung), `C` = 0,060 kWh/K per m²
  (konstanta waktu ~6 jam).
* `Q_internal` = 150 W per orang (panas tubuh + peralatan).
* `Q_AC` dibatasi kapasitas mesin (`ac_kw * COP`, COP = 3) dan dikendalikan
  proporsional terhadap galat setpoint, sehingga ruang benar-benar mencapai
  setpoint tanpa "melewati"nya.
* Suhu luar dari `data/weather.csv` (profil sinus harian 24-33 °C) plus derau
  ±0,8 °C.

### 5.3 Daya dan energi

```
P_AC  = Q_AC / COP + kipas
P_base = beban tetap (komputer, lampu) + 0,05 kW per orang + 0,008 kW/m² lampu
```

Beban tetap (basis, ~1.923 kWh/minggu) tidak bisa dihemat kebijakan, jadi
seluruh penghematan pada simulasi ini berasal dari AC.

### 5.4 Metrik keluaran

| Metrik | Makna |
|---|---|
| `energy_kwh` | Energi total (AC + beban dasar) per minggu |
| `peak_kw` | Puncak beban gedung |
| `discomfort_person_hours` | Orang-jam yang merasa terlalu panas (> 30 °C) atau terlalu dingin |
| `blocked_cooling_person_hours` | Orang-jam yang ada di ruangan tanpa pendinginan karena kebijakan |
| `policy_violations` | Peristiwa AC dinyalakan manual oleh penghuni |
| `critical_exposure_hours` | Jam ruang kritis kehilangan pendinginan (batasan keras) |

### 5.5 Asumsi (eksplisit, semua sintetis)

| Asumsi | Nilai | Alasan |
|---|---|---|
| Luas ruang | 60-150 m² | Tipikal ruang kuliah PTN |
| Daya AC terpasang | 4,0-12,0 kW per ruang | 1-4 unit split |
| COP | 3,0 | Efisiensi AC split/inverter umum |
| Kepadatan kelas | 85 % dari kapasitas | Perkiraan |
| Jadwal | Sen-Kam 08:00-16:00, Jumat 08:00-11:00, Sabtu sebagian | Konvensi kampus Indonesia |
| Perpustakaan | 08:00-21:00 (Sabtu 09:00-16:00) | Jam baca |
| Lab Biologi | 07:00-19:00, **kritis** | Contoh dari narasumber |
| Suhu luar | 24-33 °C, puncak jam 15:00 | Iklim Bengkulu |
| Tarif | Rp 1.500/kWh | Tarif listrik umum |
| Derau occupancy | 0,8-1,2 × nilai jadwal | Variasi hari nyata |

---

## 6. Hasil Analisis Kebijakan

### 6.1 Rekomendasi

`results/recommended_policy.json`:

```json
{
  "policy_id": "P020",
  "ac_start_hour": 6,
  "min_setpoint_c": 26.0,
  "lab_close_hour": 21,
  "mean_energy_kwh": 3886.38,
  "saving_vs_baseline_pct": 21.33,
  "mean_peak_kw": 120.07,
  "mean_discomfort_person_hours": 45.18,
  "discomfort_rate_pct": 0.356,
  "mean_policy_violations": 4.97,
  "mean_critical_exposure_hours": 0.0,
  "mean_cost_idr": 5829576.45
}
```

### 6.2 Dampak tiap knob

Tabel berikut adalah analisis *satu per satu*: dua knob lain dikunci pada
nilai referensi (AC mulai 07:00, setpoint 24 °C, lab tutup 20:00) lalu satu
knob diubah. Angka "hemat" dibandingkan status quo (4.939,9 kWh/minggu).

**Varian 1 - jam mulai AC** (setpoint 24 °C, lab tutup 20:00)

| Jam mulai AC | Energi (kWh/minggu) | Hemat | Ketidaknyamanan (orang-jam) | Paparan ruang kritis (jam) | Pelanggaran manual | Layak? |
|---|---|---|---|---|---|---|
| 06:00 | 4.293,3 | 13,1 % | 37,0 | 0,0 | 8,6 | ya |
| 07:00 | 4.260,8 | 13,7 % | 35,2 | 0,0 | 8,0 | ya |
| 08:00 | 4.139,3 | 16,2 % | 209,3 | 5,0 | 11,1 | **tidak** |
| 09:00 | 4.015,9 | 18,7 % | 1.437,9 | 10,0 | 23,4 | **tidak** |
| 10:00 | 3.890,8 | 21,2 % | 2.330,3 | 15,0 | 42,8 | **tidak** |

**Varian 2 - batas setpoint minimum** (AC mulai 07:00, lab tutup 20:00)

| Setpoint | Energi (kWh/minggu) | Hemat | Ketidaknyamanan (orang-jam) | Tingkat tidak nyaman | Layak? |
|---|---|---|---|---|---|
| 22 °C | 4.821,2 | 2,4 % | 30,9 | 0,24 % | ya |
| 23 °C | 4.528,5 | 8,3 % | 31,4 | 0,25 % | ya |
| 24 °C | 4.260,8 | 13,7 % | 35,2 | 0,28 % | ya |
| 25 °C | 4.028,9 | 18,4 % | 46,7 | 0,37 % | ya |
| 26 °C | 3.842,7 | 22,2 % | 60,6 | 0,48 % | **tidak** (di atas ambang) |

**Varian 3 - jam tutup lab** (AC mulai 07:00, setpoint 24 °C)

| Jam tutup lab | Energi (kWh/minggu) | Hemat | Pelanggaran manual (per minggu) | Ketidaknyamanan | Layak? |
|---|---|---|---|---|---|
| 18:00 | 4.236,2 | 14,2 % | 12,5 | 42,9 | ya |
| 19:00 | 4.243,0 | 14,1 % | 11,7 | 39,0 | ya |
| 20:00 | 4.260,8 | 13,7 % | 8,0 | 35,2 | ya |
| 21:00 | 4.275,2 | 13,5 % | 5,0 | 41,0 | ya |

### 6.3 Empat temuan

1. **Setpoint adalah knob paling efektif dan paling murah.** Menaikkan
   setpoint 22 → 25 °C menghemat 18,4 % energi dengan tambahan ketidaknyamanan
   hanya 0,13 % jam-orang, tanpa satu pun pelanggaran ruang kritis. Pada
   26 °C penghematan maksimum (22 %) tapi ketidaknyamanan menyentuh ambang -
   dan yang krusial, kombinasi itu hanya sah kalau AC boleh menyala mulai jam
   06:00 (lihat tabel 1: mulai jam 07:00 sudah melewati ambang).
2. **"Jam mulai AC" adalah kunci yang berbahaya.** Menunda AC sampai jam
   09-10 memang menghemat 19-21 % energi, tetapi langsung menimbulkan
   1.400-2.300 orang-jam ketidaknyamanan dan 10-15 jam paparan ruang
   kritis. Karena Lab Biologi mulai jam 07:00, kebijakan dengan
   `ac_start_hour >= 8` otomatis tidak layak - inilah contoh klasik batasan
   operasional yang mengalahkan optimasi energi belaka.
3. **Menutup lab terlalu cepat tidak memberi manfaat.** Menutup lab pukul
   18:00 hanya menghemat 0,5 % energi, tetapi memicu 2,5 kali lebih banyak
   peristiwa AC dinyalakan manual. Kebijakan hemat yang tidak bisa
   ditegakkan akan berubah menjadi ketidaknyamanan, komplain, dan biaya
   catering/administrasi.
4. **Rekomendasi akhir: AC mulai 06:00, setpoint 26 °C, lab tutup 21:00.**

---

## 7. Paralelisasi dan Hukum Amdahl

### 7.1 Hasil pengukuran

Diukur pada mesin lokal (Windows 11, 16 logical CPU, CPU terkuotasi), dengan
`python src/benchmark.py --reps 60` - 6.000 simulasi per titik skala:

| Pekerja | Waktu (detik) | Speedup | Efisiensi | Start up pool | Speedup *steady-state* |
|---|---|---|---|---|---|
| 1 (serial) | 26,41 | 1,00× | 100 % | - | - |
| 2 | 15,61 | 1,69× | 84,6 % | 0,21 s | 1,70× |
| 4 | 9,57 | 2,76× | 69,0 % | 0,20 s | 2,80× |
| 8 | 6,99 | 3,78× | 47,2 % | 0,20 s | 3,86× |
| 16 | 5,60 | 4,71× | 29,5 % | 0,22 s | 4,86× |

Regresi Hukum Amdahl pada data di atas menghasilkan **f = 0,841** dengan
limit speedup **6,29×**.

Sebagai pembanding, `hardware_ceiling.csv` menjalankan beban CPU murni tanpa
simulasi (start up pool dikurangkan): 1,62× pada 2 pekerja, 2,40× pada 4,
3,16× pada 8, dan 3,64× pada 16 pekerja. **Plafon mesin lokal inilah yang
membatasi scaling, bukan kode simulasi** - laptop/VM ini hanya memberi ~4 core
efektif meski melaporkan 16 logical CPU. Di node HPC sungguhan dengan 64 core
nyata, `f` akan mendekati 1 dan speedup bisa mendekati linear sampai ke batas bandwidth
memori.

Titik impas (`crossover.csv`, 8 pekerja):

| Simulasi | Serial (detik) | Paralel (detik) | Speedup |
|---|---|---|---|
| 700 | 3,26 | 1,24 | 2,63× |
| 1.400 | 6,46 | 1,92 | 3,37× |
| 2.800 | 12,78 | 3,39 | 3,77× |
| 5.600 | 25,30 | 6,47 | 3,92× |

Karena satu simulasi hanya ~4,4 ms, bahkan 700 simulasi (3 detik kerja
serial) sudah cukup untuk menang melawan biaya start up. Pada beban
kampus yang jauh lebih besar - misalnya 100 kebijakan × 1.000 pengulangan -
seluruh kurva digeser ke kanan, dan baru di situlah submitting 100 task ke
cluster benar-benar berarti.

### 7.2 Mengapa speedup tidak linear

Hukum Amdahl:

```
S(N) = 1 / ( (1 - f) + f/N )
```

karena pekerjaan tidak seluruhnya paralel: `f` adalah fraksi yang bisa
diparalelkan, dan `1 - f` adalah bagian serial (start up pool, import numpy
di tiap proses, penampungan hasil, shutdown, dan bandwidth disk yang sama).

Tiga penyebab nyata di repo ini:

1. **Start up proses.** Di Windows, `multiprocessing` memakai metode
   `spawn`: tiap pekerja adalah proses Python baru yang mengimpor ulang
   modul, termasuk numpy. Biaya ini justru bagian serial, jadi ia langsung
   memotong `f`. Di sini biayanya kecil (0,2 s), tapi di cluster dengan
   staging data bisa jauh lebih besar.
2. **Beban I/O, bukan beban komputasi.** Semua pekerja membaca file CSV
   dan menulis hasil ke disk yang sama. Titik berat muncul saat bandwidth
   disk dan scheduler OS menjadi membatasi.
3. **Batas mesin, bukan batas kode.** Pengukuran `hardware_ceiling.csv`
   menjalankan beban CPU murni tanpa simulasi. Kalau plafon mesin hanya
   3,6×, tidak ada algoritma yang bisa membuat speedup 16×. Di cluster HPC
   dengan 64 core per node dan 32 node, pekerjaan seperti ini menjadi wajar -
   dan inilah webinar yang bicara soal "jembatan": skala besar hanya mungkin
   dengan infrastruktur bersama.

Karena itu `benchmark.py` mengukur **dua** speedup: yang end-to-end (termasuk
start up) dan yang *steady-state* (start up pool dikurangi). Selisihnya
menunjukkan berapa besar bagian serialnya.

### 7.3 Titik impas

Biaya start up pool di mesin ini 0,2 s, setara dengan ~45 simulasi, jadi
paralel langsung menang sejak ukuran pekerjaan yang sangat kecil. Titik impas
akan bergeser ke kanan begitu satu simulasi lebih mahal (misalnya model yang
dihitung berhari-hari) atau start up jauh lebih mahal (misalnya di cluster
dengan 60 detik untuk staging data dan menyalin modul). Inilah bentuk
paling sering dari Hukum Amdahl yang ditemui sehari-hari - termasuk di HPC,
di mana biaya *scheduling* job bisa melampaui biaya komputasinya sendiri.

### 7.4 Dari laptop ke cluster

Pekerjaan di repo ini sengaja dirancang supaya bisa langsung dikirim ke
cluster tanpa mengubah kode:

* `hpc/job.slurm` - SLURM **array job**: satu elemen array = satu kebijakan.
  Karena setiap simulasi bebas, tiap task bisa berada di node berbeda.
* `hpc/job_single_node.slurm` - satu node, banyak core (setara
  `sweep_parallel.py`).
* `src/merge_results.py` menggabungkan CSV per-kebijakan menjadi satu file
  yang bisa dianalisis di laptop.

Perintah yang dipakai di cluster (sesuai urutan yang dijelaskan di webinar):

```bash
ssh-keygen -t ed25519            # 1. buat pasangan kunci
ssh-copy-id ~/.ssh/id_ed25519.pub user@cluster   # 2. daftarkan public key
ssh user@cluster                 # 3. masuk
sbatch --array=1-100 hpc/job.slurm   # 4. kirim job
squeue -u $USER                  # 5. pantau
scp user@cluster:.../results/sweep_results.csv results/   # 6. unduh
python src/analysis.py            # 7. analisis di komputer sendiri
```

---

## 8. Validasi

`python tests/test_model.py` menjalankan 10 uji (juga jalan di pytest):

| Uji | Yang dijamin |
|---|---|
| `test_building_loads` | 13 ruang, 168 jam, ada ruang kritis |
| `test_determinism` | seed sama → hasil sama; seed berbeda → hasil berbeda |
| `test_energy_accounting` | energi = energi AC + beban dasar (toleransi 1e-9) |
| `test_serial_matches_parallel` | hasil serial identik dengan paralel (bit per bit) |
| `test_critical_room_constraint` | `ac_start_hour=6` → 0 paparan; `=10` → paparan > 0 |
| `test_setpoint_saves_energy` | setpoint 26 < setpoint 22 (energi) |
| `test_lab_close_saves_energy` | lab tutup 17 < lab buka 23 (energi) |
| `test_policy_effect_direction` | AC lebih lambat → hemat, tapi tidak nyaman |
| `test_amdahl` | `fit_amdahl` mengembalikan `f` yang benar (galat < 0,02) |
| `test_write_and_read_results` | CSV hasil bisa dibaca kembali utuh |

---

## 9. Batasan dan Pengembangan Lanjutan

**Batasan model**

* Termal orde-1 tanpa radiant, tanpa zona, dan tanpa lag HVAC - cukup untuk
  kebijakan level gedung, tidak untuk desain HVAC.
* Perilaku penghuni direpresentasikan sebagai probabilitas, bukan agen
  individual (10.000 agen per simulasi akan menghapus efisiensi paralel).
* Data sepenuhnya sintetis. Sebelum dipakai untuk keputusan nyata, ganti
  dengan data gedung sungguhan dan kalibrasi ulang asumsi.
* Harga listrik flat Rp 1.500/kWh - belum memasukkan tarif WBP, biaya
  puncak (peak), atau reward efisiensi.

**Pengembangan lanjutan yang masuk akal**

* Ganti `data/schedules.csv` dengan jadwal nyata (formatnya sama: `room_id`,
  `day` 0-6, `start_hour`, `end_hour`, `occupancy_fraction`).
* Tambahkan transaksi harga per jam (WBP/LMP) supaya kebijakan bisa dievaluasi
  dalam rupiah, bukan hanya kWh.
* Tambah model occupant individual (Mesa) untuk menguji aturan yang berbeda
  untuk tiap jenis pengguna (dosen, mahasiswa, teknisi lab).
* Jalankan di cluster dengan `sbatch --array` dan tulis paper gaya ACM
  dengan *artifact description* seperti ajakan di webinar.

---

## 10. Kaitan dengan Webinar

| Pesan webinar | Wujud di repo ini |
|---|---|
| Bawa masalah lokal ke skala komputasi | Tagihan listrik gedung = masalah lokal, 3.030 simulasi = skala komputasi |
| Kodenya harus jalan di HPC | `hpc/job.slurm` (array job) + `merge_results.py` |
| Integrator merancang alur dari masalah ke aplikasi | `data/` → `model.py` → `sweep_*.py` → `analysis.py` → `notebooks/` |
| Semua superkomputer pakai Linux | Skrip batch memakai bash, `module load`, `srun`, `sbatch` |
|oule's HPC-AI Competition dan HPC School | Repo ini adalah bahan awal yang bisa langsung dibawa ke kompetisi |
| Tulis paper dengan artifact description | Semua asumsi, seed, dan perintah ada di README ini |
