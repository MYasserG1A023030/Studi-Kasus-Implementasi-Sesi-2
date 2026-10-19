# 2. Model Simulasi

## 2.1 Agen dan perilaku penghuni

Setiap ruang adalah satu agen yang menyimpan state internal: suhu udara, status
mesin AC, dan jumlah penghuni. Keputusan diambil per jam, lalu termal
diintegrasikan per 15 menit.

1. **Berapa banyak penghuni?** Dari jadwal ruang, ditambah ekor 1 jam untuk
   yang menuntaskan pekerjaan, ditambah lembur di lab pada malam hari,
   dikalikan derau acak 0,8-1,2 terhadap nilai jadwal.
2. **Apakah AC perlu dinyalakan?** Termostat: perlu bila suhu di atas
   setpoint. Selama beberapa waktu setelah ruang kosong, mesin menyelesaikan
   pendinginan (fase *hold*).
3. **Kalau kebijakan melarang AC menyala**, penghuni punya dua pilihan:
   menyalakan manual (peristiwa **pelanggaran kebijakan**) atau menahan diri
   (**ketidaknyamanan**). Peluangnya naik seiring bertambahnya penghuni di
   ruang, jadi kebijakan yang terlalu ketat memang encounter resistensi.
4. **Pra-pendinginan** 1 jam sebelum jadwal dimulai (kebiasaan petugas),
   hanya bisa jalan bila kebijakan mengizinkan.

## 2.2 Termal

Model RC orde-1 per ruang, dengan langkah waktu simulasi 1 jam dan integrasi
15 menit:

```
T(t+1) = T(t) + dt * ( UA*(T_out - T) + Q_internal - Q_AC ) / C
```

* `UA` = 0,010 kW/K per m2 (selubung gedung), `C` = 0,060 kWh/K per m2
  (konstanta waktu sekitar 6 jam).
* `Q_internal` = 150 W per orang (panas tubuh dan peralatan).
* `Q_AC` dibatasi kapasitas mesin (`ac_kw * COP`, COP = 3) dan dikendalikan
  proporsional terhadap galat setpoint, sehingga ruang benar-benar mencapai
  setpoint tanpa "melewati"nya.
* Suhu luar diambil dari `data/weather.csv` (profil sinus harian 24-33 C)
  ditambah derau acak plus minus 0,8 C.

## 2.3 Daya dan energi

```
P_AC   = Q_AC / COP + kipas
P_base = beban tetap (komputer, lampu) + 0,05 kW per orang + 0,008 kW/m2 lampu
```

Beban tetap (sekitar 1.923 kWh/minggu) tidak bisa dihemat kebijakan, jadi
seluruh penghematan pada simulasi ini berasal dari AC.

## 2.4 Aturan setpoint

`min_setpoint_c` pada kebijakan adalah **batas minimum** suhu AC gedung, dan
setiap ruang punya mode setpoint sendiri di `data/rooms.csv`:

| Mode | Makna | Contoh |
|---|---|---|
| `policy` | Suhu AC mengikuti setpoint kebijakan gedung | Kelas, perpustakaan, ruang dosen |
| `cap` | Ruang punya syarat suhu sendiri yang lebih dingin dan tidak boleh dilanggar | Lab Biologi (22 C), Lab Kimia (23 C) |

Untuk mode `cap`, suhu efektif adalah yang lebih dingin antara kebijakan dan
batas ruang. Inilah alasan Lab Biologi tetap menyala pada 22 C walau gedung
menetapkan 26 C.

## 2.5 Metrik keluaran

| Metrik | Makna |
|---|---|
| `energy_kwh` | Energi total (AC + beban dasar) per minggu |
| `energy_ac_kwh` | Komponen AC saja |
| `energy_base_kwh` | Komponen beban tetap |
| `peak_kw` | Puncak beban gedung |
| `discomfort_person_hours` | Orang-jam yang merasa terlalu panas (di atas 30 C) atau terlalu dingin |
| `blocked_cooling_person_hours` | Orang-jam yang ada di ruangan tanpa pendinginan karena kebijakan |
| `policy_violations` | Peristiwa AC dinyalakan manual oleh penghuni |
| `critical_exposure_hours` | Jam ruang kritis kehilangan pendinginan (batasan keras) |
| `cost_idr` | Biaya energi pada tarif Rp 1.500/kWh |

## 2.6 Asumsi model

Seluruh asumsi sintetis dan ditulis eksplisit supaya bisa diaudit.

| Asumsi | Nilai | Alasan |
|---|---|---|
| Luas ruang | 60-150 m2 | Tipikal ruang kuliah PTN |
| Daya AC terpasang | 4,0-12,0 kW per ruang | 1-4 unit split |
| COP | 3,0 | Efisiensi AC split atau inverter umum |
| Kepadatan kelas | 85 % dari kapasitas | Perkiraan |
| Jadwal | Sen-Kam 08:00-16:00, Jumat 08:00-11:00, Sabtu sebagian | Konvensi kampus Indonesia |
| Perpustakaan | 08:00-21:00 (Sabtu 09:00-16:00) | Jam baca |
| Lab Biologi | 07:00-19:00, kritis | Contoh dari narasumber |
| Suhu luar | 24-33 C, puncak jam 15:00 | Iklim Bengkulu |
| Tarif listrik | Rp 1.500/kWh | Tarif listrik umum |
| Derau occupancy | 0,8-1,2 kali nilai jadwal | Variasi hari nyata |
| Ambang ketidaknyamanan | 60 orang-jam/minggu | Batas yang disepakati manajemen dan dosen |

## 2.7 Determinisme

Seluruh simulasi diturunkan dari satu seed induk. Seed tiap simulasi dibentuk
dari `SeedSequence([seed_induk, crc32(policy_id), rep])`, sehingga:

* hasil bisa direproduksi siapa pun dari repo ini, di mesin mana pun;
* setiap kombinasi (kebijakan, pengulangan) punya aliran acak yang independen;
* tidak ada state bersama antar simulasi - syarat utama untuk paralelisasi
  tanpa lock.
