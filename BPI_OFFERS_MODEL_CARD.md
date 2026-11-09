# Simulasi Penawaran CatBoost — hasil training dari BPI

Dokumen ini menjelaskan versi awal. Model aktif sudah dilatih ulang;
hasil terbaru dan pengendalian overfitting ada di [laporan training ulang](BPI_OFFERS_RETRAINING.md).

Tiga model CatBoost terpisah dilatih dari data BPI 2019 yang disetujui pengguna.
Tidak memakai keputusan IQL/CTDE sebagai label. Setiap model memakai 30.000
item PO training dengan seed 42, paling banyak 150 pohon kedalaman 5. Early
stopping hanya memakai validasi. Semua item dalam Purchasing Document yang
sama berada pada satu partisi waktu; dokumen lintas cutoff dikeluarkan.

## Target dan sumber label

1. **Purchase**: positif = pelunasan tercatat tanpa penghapusan item. Negatif =
   penghapusan tanpa pelunasan dan tanpa reaktivasi setelah penghapusan. Kasus
   belum selesai atau ambigu tidak dianggap sebagai penolakan tawaran.
2. **Price review**: apakah `Change Price` tercatat setelah pembuatan PO pada
   kohort transaksi yang dibayar tanpa penghapusan item. Ini target revisi harga,
   tidak mengajarkan nominal penawaran balik atau hasil tawar-menawar.
3. **Payment**: jeda penerimaan invoice sampai pelunasan: <=7 hari, >7–30 hari,
   atau >30 hari. Filter hanya satu invoice dan satu pelunasan, tanpa koreksi
   invoice/debit/perubahan mata uang dan dengan urutan waktu valid. Kelompok
   tersebut tidak identik dengan perjanjian jatuh tempo atau cicilan.

Fitur: nilai PO pada event `Create Purchase Order Item`, bulan/hari pada event
tersebut, serta konteks perusahaan, vendor, kategori pembelian, jenis item dan
dokumen. Snapshot kategori/vendor diasumsikan tersedia sebagai konteks pada
awal PO; ini asumsi pemodelan karena sumber tidak menyediakan histori perubahan
semua atribut. Tidak memasukkan status akhir, invoice/pelunasan masa depan,
ID kasus, ID dokumen, atau label lain sebagai fitur.

## Hasil pengujian pertama

| Tugas | Sampel validasi | Sampel test | Accuracy | Accuracy mayoritas | Macro-F1 |
|---|---:|---:|---:|---:|---:|
| Purchase | 2.283 | 8.239 | 69,64% | 88,82% | 0,586 |
| Price review | 1.801 | 7.318 | 95,89% | 96,79% | 0,540 |
| Payment | 1.732 | 6.923 | 55,74% | 39,16% | 0,426 |

**Purchase dan Price review belum mengungguli baseline mayoritas pada accuracy.**
Price review sangat timpang; accuracy tinggi tidak berarti semua revisi dapat
dikenali. Periksa precision/recall per kelas dalam `metrics.json` dan aplikasi.
Ini model awal untuk eksperimen, belum validasi keputusan procurement optimal.
Skor keluaran dengan class weighting tidak boleh disebut peluang persetujuan
perusahaan atau bukti dampak kausal memilih vendor tersebut.

## Alur aplikasi

Pilih **Simulasi Penawaran CatBoost**, perusahaan dan konteks pembelian.
Katalog hanya menggunakan partisi training. Nilai awal adalah median nilai PO
historis per vendor/konteks, bukan harga per unit. Edit nilai tiap penawaran
sesuai skenario dan tentukan batas nilai serta tanggal skenario.

- IRE memvalidasi masukan dengan pemeriksaan teknis; tidak diklaim model IRE terlatih.
- VMI merangking kandidat berdasarkan skor model Purchase yang berada dalam batas nilai.
- DA menampilkan saran tinjauan harga hasil model Price review.
- SLM menampilkan kelompok jeda pembayaran hasil model Payment.
- Ringkasan berisi kandidat, saran lanjut/tinjau, tinjauan harga, dan perkiraan kelompok pembayaran.

Kesamaan kategori tidak membuktikan kesetaraan barang, volume, atau spesifikasi.
Tidak ada tawaran pembanding asli untuk satu pesanan. Seluruh nilai memakai
satuan BPI anonim; tidak dikonversi ke rupiah. Tidak menghitung nominal tawar
balik, cicilan 50:50, atau arus kas perusahaan yang tidak tersedia dari label ini.
Keputusan pembelian memerlukan tinjauan manusia.

## Penyimpanan dan menjalankan ulang

- `runs/bpi_offers/*.cbm`: tiga model native CatBoost.
- `runs/bpi_offers/metrics.json`: fitur, label, checksum, split dan metrik.
- `runs/bpi_offers/catalog.json`: konteks dan vendor historis dari training.
- `runs/bpi_offers/sample_manifest.csv`: ID item/dokumen/partisi/label yang dipakai.
- `runs/bpi_offers/training.sqlite3`: dataset fitur dan label serta metadata training;
  database lokal dikecualikan dari Git.
- `data/bpi_offer_audit.sqlite3`: masukan simulasi, hasil prediksi dan hash metadata.

Clone GitHub dapat menjalankan inferensi dari model, katalog, dan metadata yang
disertakan tanpa database training. Untuk ekstraksi/training ulang, impor sumber
BPI dengan `scripts/prepare_bpi.py`, kemudian jalankan
`python scripts/train_bpi_offers.py`. Periksa artefak dengan
`python scripts/check_bpi_offers.py`.

Sumber: Boudewijn van Dongen (2019), BPI Challenge 2019, 4TU.ResearchData,
CC BY 4.0; https://doi.org/10.4121/uuid:d06aff4b-79f0-45e6-8ec8-e19730c248f1.
Checksum sumber tersimpan di metadata. Tidak ada klaim perbandingan dengan
Decision Tree/SVM pada tahap ini.
