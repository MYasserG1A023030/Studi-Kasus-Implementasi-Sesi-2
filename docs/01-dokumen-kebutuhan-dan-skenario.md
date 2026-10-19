# 1. Dokumen Kebutuhan dan Skenario

## 1.1 Masalah yang dims_driven

Gedung kampus ditata dengan AC split di setiap ruang. Tagihan listrik datang
dari penghuni, bukan dari model fisik gedung. Model termal gedung saja tidak
bisa menjawab pertanyaan "kebijakan mana yang benar", karena keputusan
penghematan selalu menyentuh perilaku orang: apakah mereka menyalakan AC
sendiri saat aturan melarang, atau menahan diri dan menerima ketidaknyamanan.

Pertanyaan bisnis yang harus dijawab simulasi ini:

1. Berapa konsumsi energi mingguan gedung pada tiap kombinasi kebijakan
   (jam mulai AC, batas setpoint minimum, jam tutup lab)?
2. Kebijakan mana yang paling hemat **tanpa** melanggar batasan nyata, yaitu
   (a) ruang kritis tidak boleh kehilangan pendinginan dan (b) ketidaknyamanan
   penghuni tetap di bawah ambang yang disepakati?
3. Seberapa besar resistensi penghuni terhadap kebijakan yang terlalu ketat,
   dan apakah penghematan yang muncul masih sepadan dengan biaya penegakannya?

## 1.2 Objek yang dimodelkan

Gedung kampus dengan 13 ruang: 5 kelas kuliah, 4 laboratorium, 2 perpustakaan,
ruang dosen, dan ruang diskusi. Lab Biologi ditandai **kritis** karena
mengandung freezer dan inkubator yang tidak boleh kehilangan pendinginan
saat ruang dipakai - batasan yang tidak bisa ditawar.

## 1.3 Parameter kebijakan

| Parameter | Arti | Rentang yang diuji |
|---|---|---|
| `ac_start_hour` | Jam paling awal AC boleh menyala di gedung | 6, 7, 8, 9, 10 |
| `min_setpoint_c` | Batas suhu minimum setpoint (AC tidak boleh mendinginkan di bawah ini) | 22, 23, 24, 25, 26 °C |
| `lab_close_hour` | Jam setelahnya AC lab harus dimatikan | 18, 19, 20, 21 |

Tiga parameter ini adalah knob yang lazim dipakai manajemen gedung, dan
semuanya bisa digabung dengan aturan berbeda: misalnya Lab Biologi punya
jadwal sendiri (jam buka 07:00), sementara kelas mulai 08:00.

## 1.4 Batasan dan kriteria keberhasilan

| Batasan | Jenis | Ambang | Alasan |
|---|---|---|---|
| Paparan ruang kritis | Keras | 0 jam | Sample biologis rusak jika ruang kehilangan pendinginan saat dipakai |
| Ketidaknyamanan | Lunak | 60 orang-jam/minggu (sekitar 0,45 % jam-orang) | Batas yang disepakati manajemen dan dosen |
| Pelanggaran manual | Dipantau | 0 kejadian ideal | Indikator ketahanan kebijakan terhadap resistensi penghuni |

Kegagalan kebijakan dicatat sebagai kombinasi tiga jenis: ruang kritis yang
kena paparan, ketidaknyamanan di atas ambang, dan banyaknya peristiwa AC
yang dinyalakan penghuni secara manual di luar aturan.

## 1.5 Ukuran pekerjaan

Grid 5 × 5 × 4 = 100 kombinasi kebijakan, masing-masing 30 pengulangan acak,
ditambah 30 simulasi kebijakan status quo sebagai pembanding: **3.030
simulasi**. Setiap kombinasi (kebijakan, seed) adalah simulasi yang berdiri
sendiri - tidak ada state bersama - sehingga pekerjaannya bersifat
*embarrassingly parallel* dan bisa langsung dipetakan ke job HPC.

## 1.6 Sumber data

Seluruh data sintetis, dibuat oleh `src/make_data.py` dengan seed tetap:

| Berkas | Isi | Jumlah |
|---|---|---|
| `data/rooms.csv` | Inventaris ruang: luas, kapasitas, daya AC, syarat suhu | 13 ruang |
| `data/schedules.csv` | Jendela pemakaian per ruang per hari | 137 jendela |
| `data/weather.csv` | Suhu udara luar per jam selama satu minggu | 168 jam |
| `data/policies.csv` | Grid kebijakan + status quo | 101 kebijakan |

Untuk memakai jadwal kampus sungguhan, cukup mengganti `data/schedules.csv`
dengan skema yang sama (`room_id`, `day` 0-6, `start_hour`, `end_hour`,
`occupancy_fraction`) dan mengoreksi `data/rooms.csv`; lihat
[06-panduan-menjalankan.md](06-panduan-menjalankan.md).
