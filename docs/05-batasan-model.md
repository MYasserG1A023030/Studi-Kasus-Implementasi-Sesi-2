# 5. Batasan Model dan Pengembangan Lanjutan

## 5.1 Batasan model

* **Termal orde-1** tanpa radiant, tanpa zona, dan tanpa lag HVAC. Cukup untuk
  kebijakan level gedung, tidak untuk desain HVAC.
* **Perilaku penghuni direpresentasikan sebagai probabilitas**, bukan agen
  individual. Sepuluh ribu agen per simulasi akan menghapus efisiensi
  paralel tanpa menambah insight yang sebanding.
* **Data sepenuhnya sintetis.** Sebelum dipakai untuk keputusan nyata,
  ganti dengan data gedung sungguhan dan kalibrasi ulang asumsi.
* **Harga listrik flat** Rp 1.500/kWh, belum memasukkan tarif WBP, biaya
  puncak (peak), atau insentif efisiensi.
* **Satu minggu per simulasi** dengan cuaca sintetis, sehingga pola musiman
  dan hari raya belum ter_Model.
* **AC dimodelkan sebagai mesin dengan daya terpasang**, tanpa memodelkan
  cycling kompresor, flagging (condensat), atau scheduling keberlanjutan.

## 5.2 Pengembangan lanjutan yang masuk akal

* Ganti `data/schedules.csv` dengan jadwal nyata (formatnya sama: `room_id`,
  `day` 0-6, `start_hour`, `end_hour`, `occupancy_fraction`).
* Tambahkan transaksi harga per jam (WBP dan LMP) supaya kebijakan bisa
  dievaluasi dalam rupiah, bukan hanya kWh.
* Tambah model occupant individual (Mesa) untuk menguji aturan berbeda bagi
  tiap jenis pengguna: dosen, mahasiswa, teknisi lab.
* Modelkan harga AC per jam (hari kerja versus akhir pekan) sehingga
 mematikan Lab lebih awal benar-benar menghemat tanpa komplain.
* Jalankan di cluster dengan `sbatch --array`, lalu tulis paper gaya ACM
  dengan *artifact description* seperti ajakan di webinar.
* Uji sensitivitas asumsi: jalankan `src/benchmark.py` dan
  `src/sweep_parallel.py` dengan seed berbeda untuk mengukur dua angka
  ketidakpastian, bukan hanya rata-rata.
