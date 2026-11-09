# BPI: bukti transaksi dan persentase pembayaran per perusahaan

Pemetaan data BPI untuk vendor historis, kejadian revisi harga, dan kelompok
jeda pembayaran telah disetujui pengguna pada 8 November 2026. Persetujuan
pemetaan ini tidak mengubah definisi data asli menjadi label penerimaan tawaran.

## Hasil pemeriksaan seluruh database

Kolom `Company` yang teramati memuat **4 kode anonim**. Ini adalah kode pada
data yang diimpor; tidak mengidentifikasi nama badan hukum atau membuktikan
seluruh anak perusahaan pada deskripsi sumber terwakili secara terpisah.

Unit hitung: **item purchase order / case**, bukan jumlah tawaran vendor.
Pembilang: jumlah kasus yang memiliki setidaknya satu event `Clear Invoice`.
Penyebut: seluruh item PO dari kode perusahaan yang sama, termasuk kasus
yang pembayarannya belum tercatat. Setiap kasus dihitung sekali.

| Company | Item PO | Item dengan pelunasan tercatat | Persentase |
|---|---:|---:|---:|
| companyID_0000 | 250.686 | 183.373 | 73,15% |
| companyID_0001 | 2 | 1 | 50,00% |
| companyID_0002 | 2 | 0 | 0,00% |
| companyID_0003 | 1.044 | 303 | 29,02% |
| Total | 251.734 | 183.677 | 72,96% |

Angka ini adalah **proporsi item PO dengan pelunasan teramati**. Data dua
perusahaan hanya memiliki dua item masing-masing, sehingga persentasenya
tidak cukup untuk menyimpulkan kebijakan pembelian mereka.

Ada 234.479 kasus dengan `Record Goods Receipt` (93,15%) dan 8.839 kasus
dengan `Delete Purchase Order Item` (3,51%). Indikator tersebut tidak saling
eksklusif: 277 kasus memuat pelunasan dan penghapusan item. Karena itu
`Delete Purchase Order Item` tidak dipakai sebagai label sederhana "tawaran
ditolak"; penghapusan dapat muncul setelah aktivitas transaksi lain.

## Persentase persetujuan tawaran

Tidak dapat dihitung dari BPI ini. Rumus yang dibutuhkan adalah:

`tawaran yang diterima / seluruh tawaran yang dipertimbangkan × 100%`.

Dataset memuat PO yang sudah dibuat pada vendor historis. Seluruh tawaran
sebelum PO, termasuk penawar yang kalah atau ditolak, tidak tersedia. Nilai
72,96% tidak boleh disebut acceptance rate ataupun dipasang sebagai peluang
buyer menerima penawaran dalam simulator. Tidak adanya pelunasan juga dapat
berasal dari transaksi yang belum selesai dalam periode pengamatan.

## Implikasi untuk model

- VMI: vendor historis dipakai sebagai contoh keputusan yang teramati;
  tidak ada bukti bahwa pilihan tersebut paling optimal.
- DA: kejadian revisi harga menjadi acuan peninjauan harga. Label itu belum
  membuktikan pembeli menerima/menolak suatu nominal penawaran balik.
- SLM: jeda pembayaran aktual menjadi target kelompok waktu pembayaran.
- Keputusan membeli/tidak membeli membutuhkan definisi label tambahan.
  Jika menggunakan pembayaran teramati, nama tugasnya adalah prediksi
  pelunasan transaksi yang sudah memiliki PO; bukan penerimaan tawaran awal.

Sumber: database BPI 2019 lokal dengan SHA-256 XES
`af63bc687fc4152f2123b05c3af7772b37ef3fce2d3f67f812666c9e356baae7`.
Jumlah rinci dan indikator tumpang tindih tersimpan pada JSON pendamping.
