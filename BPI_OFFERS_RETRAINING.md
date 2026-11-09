# CatBoost penawaran — training ulang 8 November 2026

## Hasil pada periode uji yang sama

| Tugas | Accuracy awal | Accuracy baru | Macro-F1 awal | Macro-F1 baru |
|---|---:|---:|---:|---:|
| Pelunasan/penghapusan PO | 69,64% | 77,24% | 0,586 | 0,631 |
| Kejadian revisi harga | 95,89% | 94,04% | 0,540 | 0,628 |
| Kelompok jeda pembayaran | 55,74% | 62,08% | 0,426 | 0,437 |

Accuracy tidak naik untuk semua tugas. Model revisi harga dipilih karena
gabungan accuracy dan macro-F1 pada validasi; pemilihan hanya berdasarkan
accuracy akan mudah mengabaikan kejadian revisi yang jarang. Ini tetap model
pendekatan hasil transaksi, bukan bukti penerimaan tawaran atau strategi optimal.

## Mengurangi risiko overfitting

- Memakai seluruh partisi training yang memenuhi label: 93.943 kasus Purchase,
  89.730 Price review, dan 86.142 Payment, menggantikan sampel 30.000 per tugas.
- Item dari Purchasing Document yang sama berada pada satu partisi waktu.
  Dokumen melintasi cutoff tetap dikeluarkan sesuai protokol sebelumnya.
- Pohon dibatasi kedalamannya, L2 diperkuat, seed tetap, dan early stopping
  memilih jumlah pohon dari validasi. Maksimal 350 iterasi untuk kandidat awal.
- Empat konfigurasi awal dibandingkan dengan model sebelumnya pada validasi.
  Threshold klasifikasi biner juga dipilih pada validasi.
- Skor pemilihan: `0.65 * accuracy validasi + 0.35 * macro-F1 validasi`.
- Payment awal menunjukkan macro-F1 train–validasi berbeda lebih dari 0,15.
  Kandidat tambahan kedalaman 2/3 dengan L2 40/80 diuji. Hanya kandidat yang
  lolos batas selisih accuracy 0,08 dan macro-F1 0,15 boleh dipilih.
- Payment terpilih memakai kedalaman 3 dan L2 40, 119 pohon dengan early
  stopping. Model Purchase terpilih memakai 246 pohon; Price review 350 pohon.
- Script training ulang berikutnya menerapkan pemeriksaan selisih train–validasi
  sebelum memilih model, termasuk kandidat sederhana untuk Payment.

Tidak ada jaminan model bebas overfitting. Purchase dan Payment masih memiliki
penurunan accuracy lebih dari 8 poin dari validasi ke periode uji. Aplikasi
menampilkan peringatan tersebut, metrik per kelas dan kurva loss train/validasi.
Lolos batas selisih train–validasi adalah pemeriksaan terbatas, bukan bukti
generalisasi sempurna.

Periode uji lama dipertahankan untuk perbandingan. Data uji tidak dipakai untuk
memilih hyperparameter/threshold/checkpoint. Evaluasi tambahan setelah
diagnostik Payment tetap memakai periode uji yang sama; hasil ini bukan
pengujian eksternal baru yang independen. Interval accuracy 95% dihitung
dengan bootstrap per Purchasing Document dan disimpan di metadata.

## Hasil ketika perusahaan menyelesaikan pembayaran

Panel **Hasil transaksi perusahaan yang sudah dibayar** menampilkan bukti
historis BPI, terpisah dari hasil simulasi penawaran baru.

- Kohort: tepat satu penerimaan invoice dan satu pelunasan; tanpa penghapusan
  item, pembatalan/koreksi invoice, debit memo atau perubahan mata uang;
  urutan event/waktu valid dan nilai PO awal positif.
- companyID_0000: **171.654** kasus yang memenuhi filter.
- companyID_0003: **293** kasus yang memenuhi filter.
- Total: **171.947**. Tampilan berisi maksimal 200 kasus terbaru per perusahaan.
- Tabel memuat ID kasus, vendor, kategori, nilai PO anonim, tanggal invoice,
  tanggal pelunasan, jeda pembayaran, revisi harga yang tercatat dan status aktual.
- Tombol perbandingan memakai hanya fitur saat PO dibuat; tanggal pelunasan
  dan hasil aktual tidak dimasukkan ke fitur model.
- Tabel dapat diunduh sebagai CSV. Cuplikan JSON dikemas bersama model agar
  hasil clone juga dapat menampilkan bukti historis tanpa database training.

Pelunasan satu invoice tercatat bukan bukti semua kewajiban perusahaan selesai.
Kasus dari perusahaan lain yang tidak memenuhi filter tidak dibuat-buat.
Simulasi baru tetap menghasilkan saran, bukan catatan transaksi nyata yang selesai.

## Artefak dan reproduksi

Model aktif: `runs/bpi_offers/`. Versi lama dicadangkan pada
`runs/bpi_offers_before_retrain_20261108/`. Data/audit lama tidak dihapus.

- `metrics.json`: hasil, threshold, kandidat validasi, kurva, batas waktu,
  peringatan generalisasi dan checksum tiga model.
- `completed_transactions.json`: bukti hasil transaksi BPI yang sudah dilunasi.
- `training.sqlite3`: fitur, label, daftar sampel evaluasi dan metadata terbaru.
- `sample_manifest.csv`: seluruh item/dokumen/partisi/label yang digunakan.

Contoh training ulang ke direktori kandidat baru:

```powershell
python scripts/retrain_bpi_offers.py --previous runs/bpi_offers --out runs/bpi_offers_candidate
```

Kandidat tidak otomatis mengganti model aktif. Periksa laporan validasi dan
peringatan generalisasi sebelum publikasi. Script regularisasi Payment dan
finalisasi diagnostik disertakan sebagai catatan eksperimen versi ini.
