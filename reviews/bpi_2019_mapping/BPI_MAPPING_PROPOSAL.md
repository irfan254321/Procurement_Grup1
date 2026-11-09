# Usulan pemetaan BPI 2019 untuk simulasi agen

Status: **MENUNGGU PERSETUJUAN PENGGUNA**. Belum digunakan untuk training baru
atau untuk mengganti keputusan simulator. Semua jumlah di bawah dihitung dari
database BPI yang diimpor, bukan perkiraan dari deskripsi dataset.

## Data yang sudah diperiksa

- 251.734 item PO, 1.595.923 event, 1.975 vendor anonim.
- Checksum XES SHA-256: `af63bc687fc4152f2123b05c3af7772b37ef3fce2d3f67f812666c9e356baae7`.
- Sumber: https://doi.org/10.4121/uuid:d06aff4b-79f0-45e6-8ec8-e19730c248f1
- Atribusi: Boudewijn van Dongen (2019), BPI Challenge 2019, 4TU.ResearchData, CC BY 4.0.

## Usulan keputusan per agen

| Agen | Data yang dipilih | Label yang diusulkan | Makna dan batasan |
|---|---|---|---|
| IRE | Event `Change Quantity`: 17.590 kasus | Ada/tidak ada revisi jumlah yang tercatat | Mempelajari kecenderungan revisi permintaan. Jumlah unit lama/baru dan porsi mendesak tidak tersedia. |
| VMI | 251.734 `Create Purchase Order Item`, vendor dan kategori historis | ID vendor yang dipilih dalam riwayat | Meniru pemilihan vendor historis pada kategori sejenis. Nilai PO dipakai sebagai konteks transaksi, bukan harga per unit atau tawaran kompetitif. |
| DA | 12.423 `Change Price` pada 11.224 kasus | Ada/tidak ada revisi harga yang tercatat | Mengusulkan peninjauan harga berdasarkan pola historis. Tidak melatih nominal penawaran balik atau keberhasilan negosiasi. |
| SLM | 172.197 kasus dengan tepat satu invoice dan satu pelunasan yang lolos filter | Jeda pembayaran <=7 hari, >7–30 hari, >30 hari | Mempelajari perilaku pembayaran historis. Batas 7/30 hari adalah rancangan usulan, bukan termin kontrak asli. |

Ini memungkinkan alur antarmuka yang menyerupai MARL: **input permintaan → IRE
→ VMI → DA → SLM → ringkasan keputusan**. Nama aksi mengikuti makna label di
atas. Nominal tawar balik serta jadwal cicilan tidak dihasilkan dari label yang
tidak tersedia. CatBoost akan dilatih untuk tugas yang disepakati, menggunakan
data BPI; keputusan IQL/CTDE tidak dipakai sebagai pengganti sumber label.

### 1. Vendor / calon tawaran awal

Tabel `vendor_transactions` menyimpan vendor yang benar-benar tercatat pada
event pembuatan item PO, nilai kumulatif yang diamati, kategori, perusahaan,
ID kasus dan indeks event sumber. Ada 189 kelompok gabungan perusahaan,
spend area, sub-spend area dan item type yang memiliki lebih dari satu vendor
historis. Kelompok tersebut dapat menjadi titik awal penyaringan kandidat;
kesamaan kategori belum membuktikan barang, volume, kapasitas atau tawarannya
setara. Tidak boleh menyimpulkan vendor termurah/terbaik dari nilai PO saja.

Contoh asli: kasus `2000000000_00001`, vendor `vendorID_0000`, kategori
Facility Management, nilai pada pembuatan PO **298 satuan EUR anonim**.
Kasus `2000000002_00001`, vendor `vendorID_0002`, kategori Digital Marketing,
nilainya **76.210**. Kedua transaksi ini tidak layak dibandingkan sebagai dua
tawaran untuk barang yang sama. Kode vendor BPI dipertahankan; tidak dianggap
sebagai vendor A/B/C pada fixture laporan.

### 2. Tawar balik / revisi harga

Ada 12.423 event `Change Price`, tetapi **12.416 event mempunyai nilai tersimpan
yang sama dengan event tepat sebelumnya**. Tujuh sisanya menunjukkan nilai
lebih kecil; semuanya mengikuti `Record Invoice Receipt`, sehingga perbedaan
nilai dapat mencerminkan perbedaan konteks invoice/PO, bukan besaran konsesi.

Contoh: kasus `2000000010_00001`, event 20, nilai sebelum dan setelah event
`Change Price` sama-sama **1.668.264**. Informasi yang dapat dipelajari adalah
kejadian revisi harga, bukan penawaran awal 1.668.264 lalu penawaran balik baru.

Usulan DA: klasifikasi **risiko/kebutuhan tinjauan harga**. CatBoost memprediksi
apakah revisi pernah tercatat setelah titik keputusan. Label nol berarti
tidak ada revisi yang teramati dalam periode data; bukan bukti penawaran
diterima atau transaksi optimal. Untuk label negatif awal, gunakan transaksi
dengan `Clear Invoice`: 174.606 kasus tanpa revisi harga dan 9.071 dengan revisi.
Pemilihan kasus yang sudah dibayar membawa bias terhadap transaksi selesai
dan harus dijelaskan saat evaluasi. Fitur hanya dari prefix sebelum target;
status pembayaran akhir digunakan untuk membentuk kohort/label, bukan fitur.

### 3. Termin / perilaku pembayaran

Ada **7 event literal `Change payment term`**, pada 7 item PO. Event tersebut
tidak menyediakan nilai termin lama dan baru. Jumlah ini tidak cukup menjadi
dasar tunggal model termin yang dapat digeneralisasi.

Usulan yang datanya lebih banyak: ukur jeda `Record Invoice Receipt` sampai
`Clear Invoice`, dengan persetujuan bahwa targetnya adalah **jeda pembayaran
historis**, bukan perjanjian jatuh tempo atau pembayaran dini yang optimal.

| Label usulan | Definisi persis | Jumlah kasus |
|---|---|---:|
| Pembayaran dalam 7 hari | 0 <= jeda <= 7 hari | 7.469 |
| Pembayaran lebih dari 7 hingga 30 hari | 7 < jeda <= 30 hari | 56.604 |
| Pembayaran lebih dari 30 hari | jeda > 30 hari | 108.124 |
| Total lolos | | 172.197 |

Filter: tepat satu penerimaan invoice dan satu `Clear Invoice`, urutan event
dan waktu valid, tanpa pembatalan invoice, debit memo, subsequent invoice atau
perubahan mata uang. Kasus multi-invoice/multi-pelunasan dikeluarkan karena log
ini tidak menyediakan ID invoice yang cukup untuk mencocokkannya dengan aman.
28.086 kasus memiliki invoice tetapi belum memiliki `Clear Invoice` yang
teramati; tidak diberi label pembayaran >30 hari secara otomatis.

Contoh: `2000000000_00001` memiliki jeda **23,22 hari**, sehingga masuk kategori
>7–30 hari. `2000000002_00001` memiliki jeda **0,10 hari**, kategori <=7 hari.
Tanggal pembayaran aktual hanya dipakai membentuk target training. Untuk
prediksi baru, informasi tersebut tidak dimasukkan sebagai fitur.

**Tidak ada label cicilan 50:50 yang dapat disahkan dari ekstraksi ini.** Banyak
pelunasan dalam satu PO tidak otomatis membuktikan cicilan satu invoice.

## Keputusan yang diminta

Setujui atau revisi pemetaan berikut sebelum training baru:

1. VMI belajar pilihan vendor historis; nilai transaksi adalah pendekatan
   konteks tawaran awal, dengan penyaringan kategori yang disepakati.
2. DA belajar kejadian revisi harga; hasilnya berupa saran peninjauan harga,
   tanpa nominal tawar balik buatan.
3. SLM belajar tiga kelompok jeda pembayaran aktual dengan batas 7/30 hari,
   tanpa mengklaimnya sebagai termin kontrak atau jadwal cicilan.
4. IRE belajar pola revisi jumlah yang tercatat; porsi unit mendesak tetap
   membutuhkan definisi simulasi tambahan bila ingin dipakai.

Persetujuan atas pemetaan ini mengubah makna aksi simulator dari aksi fixture
lama menjadi keputusan turunan data BPI. Kesamaan alur layar tidak berarti
data BPI memiliki seluruh label asli MARL. Pemisahan train/validation/test
tetap dikelompokkan per Purchasing Document dan waktu; tidak menggunakan
kejadian masa depan sebagai fitur. Accuracy mengukur kecocokan keputusan
historis, bukan bukti penghematan atau optimalitas.

## Berkas untuk peninjauan

- `data/bpi_mapping_review.sqlite3`: tabel kandidat terpisah, status pending.
- `reviews/bpi_2019_mapping/BPI_MAPPING_REVIEW.json`: jumlah, aturan dan contoh.
- `scripts/export_bpi_mapping_review.py`: ekstraksi ulang yang dapat direproduksi.
- Database sumber BPI dan checkpoint CatBoost yang ada tidak diubah.
