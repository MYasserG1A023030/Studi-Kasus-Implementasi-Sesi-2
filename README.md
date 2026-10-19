# Studi Kasus Implementasi Sesi 2

Studi kasus implementasi yang disusun dari materi *Informatics Practitioner
Lecture Series "Bridging Global Infrastructure to Address Local Challenges in
HPC"* (Program Studi Informatika, Universitas Bengkulu; narasumber Dr.
Worawan Diaz Carballo, Thammasat University). Repo ini berisi simulasi
berbasis agen untuk kebijakan penghematan listrik gedung kampus, pipeline
Python yang dapat dijalankan ulang, dan seluruh keluaran analisis.

| Isi repo | Keterangan |
| --- | --- |
| `src/`, `run_all.py` | Tujuh modul Python (simulator agen, pembuat data, sweep serial dan paralel, benchmark Amdahl, analisis, penggabung hasil) beserta orkestratornya |
| `docs/` | Enam dokumen: kebutuhan dan skenario, model simulasi, hasil dan rekomendasi, paralelisasi dan HPC, batasan model, panduan menjalankan |
| `results/` | 3.030 baris hasil simulasi, ringkasan 101 kebijakan, tabel waktu/speedup/impas, dan 4 grafik |
| `data/` | Data sintetis: inventaris 13 ruang, jadwal pemakaian, cuaca mingguan, dan grid 100 kebijakan |
| `hpc/` | Dua batch script SLURM (array job per kebijakan, dan satu node banyak core) plus panduan alur kerja HPC |
| `tests/` | 10 uji kebenaran: determinisme, kesetaraan serial-paralel, neraca energi, dan kepatuhan batasan ruang kritis |

## Simulasi Berbasis Agen Kebijakan Penghematan Listrik Gedung Kampus

Ide diambil dari webinar: *"simulasi penghematan listrik gedung dengan
memodelkan perilaku manusia"*. Model fisik gedung saja tidak cukup, karena
tagihan listrik datang dari penggunanya. Repo ini mensimulasikan **perilaku
penghuni** di atas model termal gedung, lalu menguji kebijakan penghematan
sebelum diterapkan - dengan perhitungan yang sengaja dirancang untuk
dijalankan paralel di HPC.

| Aspek | Nilai |
| --- | --- |
| Objek | Gedung kampus, 13 ruang: 5 kelas, 4 lab, 2 perpustakaan, ruang dosen, ruang diskusi |
| Periode simulasi | 1 minggu (168 jam), integrasi termal per 15 menit |
| Data | 13 ruang, 137 jendela jadwal, 168 jam cuaca, 101 kebijakan |
| Sasaran | Hemat energi tanpa melanggar batasan ruang kritis dan batas ketidaknyamanan penghuni |
| Batasan keras | 0 jam paparan ruang kritis (Lab Biologi, 07:00-19:00) |
| Tool | Python 3.11 (numpy, pandas, matplotlib, joblib) |

## Temuan utama (dihitung otomatis oleh pipeline)

- **Setpoint adalah knob paling murah.** Menaikkan setpoint 22 menjadi 25 C
  menghemat **18,4 %** energi dengan tambahan ketidaknyamanan hanya 0,13 poin
  persen, dan tidak menyentuh batasan ruang kritis sama sekali.
- **Jam mulai AC adalah kunci yang berbahaya.** Menunda AC ke jam 09-10
  terlihat hemat 19-21 %, tetapi langsung menimbulkan **1.400-2.300 orang-jam**
  ketidaknyamanan dan **10-15 jam** ruang kritis tanpa pendinginan. Karena Lab
  Biologi mulai jam 07:00, semua kebijakan dengan `ac_start_hour` 8 ke atas
  otomatis tidak layak.
- **Menutup lab terlalu cepat tidak memberi manfaat.** Menutup lab pukul
  18:00 hanya menghemat 0,5 % energi, tetapi memicu **2,5 kali** lebih banyak
  peristiwa AC dinyalakan manual. Kebijakan hemat yang tidak bisa ditegakkan
  berubah menjadi komplain dan biaya administrasi.
- **Energi termurah belum tentu kebijakan terbaik.** Kandidat `P017` (hemat
  22,0 %) memicu 2,4 kali lebih banyak pelanggaran manual dibanding `P020`
  (hemat 21,3 %); selisih energinya cuma 0,9 %.
- **Rekomendasi: AC mulai 06:00, setpoint 26 C, lab tutup 21:00.** Hemat
  **21,3 %** atau Rp 1.580.324 per minggu, tanpa paparan ruang kritis, dengan
  ketidaknyamanan 45,2 orang-jam/minggu (0,36 % jam-orang).
- **Paralelisasi bekerja, tapi dibatasi mesin.** 6.000 simulasi: serial
  27,22 detik menjadi 7,06 detik pada 8 pekerja (**3,86x**) dan 5,64 detik
  pada 16 pekerja (**4,83x**). Regresi Amdahl memberi **f = 0,846** dengan
  limit 6,49x, sementara probe beban CPU murni menunjukkan plafon mesin
  lokal hanya **3,59x** - jadi saturasi berasal dari batas CPU laptop atau VM,
  bukan dari kode.

## Cara menjalankan

```bash
cd Studi-Kasus-Implementasi-Sesi-2
python -m pip install -r requirements.txt
python run_all.py
```

Seluruh pipeline berjalan sekitar 2,5 menit dan menulis keluarannya ke
`results/`. Pipeline bisa dipercepat dengan `python run_all.py
--skip-benchmark` bila tahap benchmark tidak dibutuhkan. Detail lengkap ada
di [docs/06-panduan-menjalankan.md](docs/06-panduan-menjalankan.md).

## Struktur folder

```
Studi-Kasus-Implementasi-Sesi-2/
├── run_all.py                  # orkestrasi semua tahap
├── requirements.txt
├── .gitignore
├── src/                        # paket simulasi
│   ├── model.py                 # simulator: agen ruang, termal, kebijakan, metrik
│   ├── make_data.py             # generator data sintetis (rooms/schedules/weather/policies)
│   ├── sweep_serial.py          # sweep serial (baseline kecepatan + sumber kebenaran)
│   ├── sweep_parallel.py        # sweep paralel (multiprocessing / joblib)
│   ├── benchmark.py             # uji skala: speedup, efisiensi, Amdahl, titik impas
│   ├── analysis.py              # ringkasan kebijakan, rekomendasi, grafik
│   └── merge_results.py         # gabungkan CSV per-kebijakan (hasil SLURM array job)
├── hpc/                        # batch script HPC
│   ├── job.slurm                # SLURM array job: 1 task = 1 kebijakan
│   ├── job_single_node.slurm    # 1 node, banyak core
│   └── README.md                # alur kerja HPC (kunci SSH, sbatch, unduh hasil)
├── data/                       # data sintetis (dapat diganti data nyata)
│   ├── rooms.csv                # inventaris 13 ruang
│   ├── schedules.csv            # 137 jendela pemakaian per hari
│   ├── weather.csv              # suhu udara luar per jam (168 jam)
│   └── policies.csv             # grid 100 kebijakan + status quo
├── results/                    # keluaran pipeline
│   ├── sweep_results.csv        # 1 baris per (kebijakan, pengulangan)
│   ├── policy_summary.csv       # ringkasan per kebijakan
│   ├── recommended_policy.json  # kebijakan rekomendasi beserta alasannya
│   ├── timings.csv              # waktu serial vs paralel
│   ├── speedup.csv              # speedup, efisiensi, parameter Amdahl
│   ├── crossover.csv            # titik impas serial vs paralel
│   ├── hardware_ceiling.csv     # batas scaling mesin lokal
│   └── figures/                 # 4 grafik hasil analisis
├── notebooks/analysis.ipynb    # analisis interaktif + grafik
├── tests/test_model.py         # 10 uji kebenaran (jalan tanpa pytest)
└── docs/                       # dokumen metodologi dan rekomendasi
```

## Dokumentasi

| Dokumen | Isi |
| --- | --- |
| [01-dokumen-kebutuhan-dan-skenario.md](docs/01-dokumen-kebutuhan-dan-skenario.md) | Masalah, objek yang dimodelkan, parameter kebijakan, batasan, dan sumber data |
| [02-model-simulasi.md](docs/02-model-simulasi.md) | Agen dan perilaku penghuni, model termal, aturan setpoint, metrik, dan tabel asumsi |
| [03-hasil-dan-rekomendasi.md](docs/03-hasil-dan-rekomendasi.md) | Ringkasan per kebijakan, analisis sensitivitas tiap knob, temuan, dan grafik |
| [04-paralelisasi-dan-hpc.md](docs/04-paralelisasi-dan-hpc.md) | Hasil pengukuran speedup, Hukum Amdahl, titik impas, dan cara menjalankan di cluster |
| [05-batasan-model.md](docs/05-batasan-model.md) | Batasan model, pengembangan lanjutan, dan uji sensitivitas yang disarankan |
| [06-panduan-menjalankan.md](docs/06-panduan-menjalankan.md) | Cara menjalankan, keluaran, opsi perintah, dan cara mengganti data dengan data nyata |

## Catatan integritas data

Seluruh data dalam studi kasus ini adalah **data sintetis** yang dibuat oleh
`src/make_data.py` dengan seed tetap, sehingga hasil selalu reproducible.
Tidak ada data nyata gedung, mahasiswa, atau laboratorium yang dipakai.
Cuaca, jadwal, dan profil penghuni semuanya asumsi yang dinyatakan
eksplisit di [docs/02-model-simulasi.md](docs/02-model-simulasi.md) bagian
2.6, sehingga setiap angka bisa ditelusuri ke asumsinya.
