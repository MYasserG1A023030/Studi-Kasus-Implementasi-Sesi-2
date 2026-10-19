# 3. Hasil dan Rekomendasi

Seluruh angka pada dokumen ini dihasilkan otomatis oleh `src/analysis.py`
dari `results/sweep_results.csv` (3.030 baris: 101 kebijakan x 30 pengulangan
acak). Tidak ada angka yang ditulis tangan.

## 3.1 Ringkasan per kebijakan

| Besaran | Status quo | Kebijakan rekomendasi | Selisih |
|---|---|---|---|
| Energi | 4.939,9 kWh/minggu | 3.886,4 kWh/minggu | -21,3 % |
| Biaya (Rp 1.500/kWh) | Rp 7.409.900/minggu | Rp 5.829.576/minggu | -Rp 1.580.324/minggu |
| Puncak beban | 124,8 kW | 120,1 kW | -3,8 % |
| Ketidaknyamanan | 22,7 orang-jam/minggu | 45,2 orang-jam/minggu | +22,5 |
| Pelanggaran manual | 0,0 per minggu | 5,0 per minggu | +5,0 |
| Paparan ruang kritis | 0,0 jam | 0,0 jam | 0 |

Rekomendasi: **AC boleh menyala mulai jam 06:00, setpoint minimum gedung
26 C, lab ditutup pukul 21:00** (`P020`).

Dari 101 kebijakan yang dievaluasi, 37 memenuhi dua batasan (tidak ada
paparan ruang kritis dan ketidaknyamanan di bawah ambang 60 orang-jam/minggu).
Kandidat dengan energi paling rendah (`P017`, hemat 22,0 %) ternyata memicu
2,4 kali lebih banyak peristiwa AC dinyalakan manual; `P020` hanya 0,9 % lebih
boros tetapi jauh lebih mudah ditegakkan - dan itu yang direkomendasikan.

Isi lengkap `results/recommended_policy.json`:

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

## 3.2 Dampak tiap knob

Analisis satu per satu: dua knob lain dikunci pada nilai referensi (AC mulai
07:00, setpoint 24 C, lab tutup 20:00) lalu satu knob diubah. Angka "hemat"
dibandingkan status quo (4.939,9 kWh/minggu).

### 3.2.1 Jam mulai AC (setpoint 24 C, lab tutup 20:00)

| Jam mulai AC | Energi (kWh/minggu) | Hemat | Ketidaknyamanan (orang-jam) | Paparan ruang kritis (jam) | Pelanggaran manual | Layak? |
|---|---|---|---|---|---|---|
| 06:00 | 4.293,3 | 13,1 % | 37,0 | 0,0 | 8,6 | ya |
| 07:00 | 4.260,8 | 13,7 % | 35,2 | 0,0 | 8,0 | ya |
| 08:00 | 4.139,3 | 16,2 % | 209,3 | 5,0 | 11,1 | tidak |
| 09:00 | 4.015,9 | 18,7 % | 1.437,9 | 10,0 | 23,4 | tidak |
| 10:00 | 3.890,8 | 21,2 % | 2.330,3 | 15,0 | 42,8 | tidak |

### 3.2.2 Batas setpoint minimum (AC mulai 07:00, lab tutup 20:00)

| Setpoint | Energi (kWh/minggu) | Hemat | Ketidaknyamanan (orang-jam) | Tingkat tidak nyaman | Layak? |
|---|---|---|---|---|---|
| 22 C | 4.821,2 | 2,4 % | 30,9 | 0,24 % | ya |
| 23 C | 4.528,5 | 8,3 % | 31,4 | 0,25 % | ya |
| 24 C | 4.260,8 | 13,7 % | 35,2 | 0,28 % | ya |
| 25 C | 4.028,9 | 18,4 % | 46,7 | 0,37 % | ya |
| 26 C | 3.842,7 | 22,2 % | 60,6 | 0,48 % | tidak (di atas ambang) |

### 3.2.3 Jam tutup lab (AC mulai 07:00, setpoint 24 C)

| Jam tutup lab | Energi (kWh/minggu) | Hemat | Pelanggaran manual (per minggu) | Ketidaknyamanan | Layak? |
|---|---|---|---|---|---|
| 18:00 | 4.236,2 | 14,2 % | 12,5 | 42,9 | ya |
| 19:00 | 4.243,0 | 14,1 % | 11,7 | 39,0 | ya |
| 20:00 | 4.260,8 | 13,7 % | 8,0 | 35,2 | ya |
| 21:00 | 4.275,2 | 13,5 % | 5,0 | 41,0 | ya |

## 3.3 Empat temuan

1. **Setpoint adalah knob paling efektif dan paling murah.** Menaikkan
   setpoint 22 menjadi 25 C menghemat 18,4 % energi dengan tambahan
   ketidaknyamanan hanya 0,13 poin persen, tanpa satu pun pelanggaran ruang
   kritis. Pada 26 C penghematan maksimum (22 %) tapi ketidaknyamanan menyentuh
   ambang - dan yang krusial, kombinasi itu hanya sah kalau AC boleh menyala
   mulai jam 06:00 (mulai jam 07:00 sudah melewati ambang).
2. **Jam mulai AC adalah kunci yang berbahaya.** Menunda AC sampai jam 09-10
   memang menghemat 19-21 % energi, tetapi langsung menimbulkan 1.400-2.300
   orang-jam ketidaknyamanan dan 10-15 jam paparan ruang kritis. Karena Lab
   Biologi mulai jam 07:00, kebijakan dengan `ac_start_hour` 8 ke atas
   otomatis tidak layak - inilah contoh klasik batasan operasional yang
   mengalahkan optimasi energi belaka.
3. **Menutup lab terlalu cepat tidak memberi manfaat.** Menutup lab pukul
   18:00 hanya menghemat 0,5 % energi, tetapi memicu 2,5 kali lebih banyak
   peristiwa AC dinyalakan manual. Kebijakan hemat yang tidak bisa ditegakkan
   akan berubah menjadi ketidaknyamanan, komplain, dan biaya administrasi.
4. **Rekomendasi akhir: AC mulai 06:00, setpoint 26 C, lab tutup 21:00.**

## 3.4 Grafik pendukung

| Berkas | Isi |
|---|---|
| `results/figures/profil_beban_harian.png` | Profil beban 24 jam, status quo versus rekomendasi |
| `results/figures/frontier_kebijakan.png` | Frontier energi versus ketidaknyamanan, seluruh kebijakan dan zoom daerah layak |
| `results/figures/peta_panas_kebijakan.png` | Peta panas energi untuk kombinasi jam mulai AC dan jam tutup lab |
| `results/figures/speedup.png` | Kurva speedup, efisiensi, Amdahl, dan plafon mesin |

Notebook `notebooks/analysis.ipynb` memuat ulang seluruh keluaran dan
menghasilkan grafik yang sama secara interaktif.
