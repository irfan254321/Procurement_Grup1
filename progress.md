# Progress proyek

## Komentar pembelajaran dan katalog file Python (29 September 2026)

- [x] Komentar pembuka berbahasa Indonesia ditambahkan pada 35 file Python; komentar rinci dekat logika utama Streamlit, layanan, SQLite, vendor, IQL, CTDE, baseline, dan environment.
- [x] `docs/PANDUAN_FILE_PYTHON.md` menjelaskan fungsi seluruh file Python, peta alur, sintaks penting, dan urutan belajar. README menautkannya.
- [x] Pemeriksaan sintaks lulus; 20 tes lulus; 35/35 file Python mempunyai komentar pengantar. ZIP unduhan diperbarui.

Dokumen ini mencatat pekerjaan aktif agar sesi berikutnya dapat melanjutkan dari keadaan terakhir. Baca file ini sebelum mengubah kode.

## Tugas aktif: error Arrow dan 20 skenario (29 September 2026)

Pengguna melaporkan `ArrowTypeError` pada kolom `Putaran` dan meminta 20 skenario uji dengan alasan perubahan yang rinci. CSV `2026-09-29T11-22_export.csv` adalah run IQL model 7, 700 unit, biaya Rp68.892.600, kas akhir bulan 2 Rp11.107.400, status LAYAK dengan peringatan kas rendah. Gambar menunjukkan XGBoost `TIDAK OPTIMAL` probabilitas 3,9%; itu klasifikasi baseline yang berbeda dari pemeriksaan kelayakan.

- [x] Penyebab Arrow ditemukan: tabel putaran mencampur `"Awal"` (str) dan nomor ronde (int). Nomor ronde sudah diubah menjadi `str` pada salinan kerja `app.py`.
- [x] Tes regresi mengonversi tabel putaran nyata ke PyArrow; 20 tes keseluruhan lulus.
- [x] Jalankan 20 skenario model 7 dengan input/metode/seed/vendor yang bervariasi, tanpa menambah riwayat SQLite pengguna; hasil di `runs/demo_scenarios_v7.json`.
- [x] Tulis `docs/20_skenario_uji.md` berisi input, perubahan, tujuan, hasil aktual, dan cara membaca perbedaan. Uji transport B mengungkap sensitivitas kebijakan yang masih lemah.
- [x] Sinkronkan delapan file ke proyek utama tanpa menimpa SQLite; 20 tes di proyek utama lulus. ZIP proyek diperbarui.

## Status terkini: pengembalian aturan kas (permintaan 29 September 2026)

Pengguna meminta kembali ke perilaku sebelum v0.9.0 karena target kas Rp60 juta sebagai syarat wajib membuat terlalu banyak skenario tidak layak. Kas Rp60 juta sekarang kembali **peringatan**; kas negatif, anggaran, kapasitas, dan tenggat tetap syarat wajib.

- [x] Tinjau `2026-09-29T11-05_export.csv`: saldo akhir Rp21.077.800 positif, tetapi v6 menolaknya hanya karena di bawah Rp60 juta.
- [x] `config/report_scenario.yaml` dan `config/env_default.yaml` mengatur `enforce_min_cash: false`.
- [x] Versi proyek 0.10.0 / model 7; test baru menegaskan kas positif di bawah target menghasilkan peringatan dan rencana dapat layak.
- [x] IQL dan CTDE model 7 (20.000 episode seed 0) selesai; konsensus 71,0%/72,8% pada 500 skenario. Baseline ML dilatih ulang; XGBoost accuracy 79,7%, F1 65,1%, ROC-AUC 0,842.
- [x] Evaluasi kualitas 100 skenario terpisah: pembanding menemukan 76 feasible; IQL melewatkan 2, CTDE 0; selisih biaya rata-rata 3,45%/2,32%. README dan dokumen alur sudah diperbarui.
- [x] 19 tes lulus; Streamlit AppTest startup dan skenario baru masing-masing 0 exception.
- [x] 23 file disinkronkan ke proyek utama tanpa menimpa SQLite; 19 tes di proyek utama lulus dan model IQL/CTDE keduanya versi 7.
- [x] ZIP distribusi diperbarui dan diverifikasi memuat model/evaluasi v7 serta progress.md, tanpa database pengguna.

## Cara memeriksa hasil terbaru

Jalankan contoh 600 unit, 100 unit mendesak, anggaran Rp100 juta, seed 0. IQL dan CTDE model 7 menghasilkan LAYAK dengan kas positif di bawah Rp60 juta, sehingga UI harus menampilkan peringatan likuiditas. Contoh BAB 6 awal tetap TIDAK FEASIBLE karena dana total tidak cukup.

## Riwayat v0.9.0 (arsip, bukan status aturan saat ini)

## Tujuan aktif (29 September 2026)

- Selaraskan status kelayakan dengan syarat likuiditas laporan: kas akhir setiap bulan minimal Rp60 juta pada skenario BAB 6.
- Pastikan diagnosis tidak feasible memperhitungkan kas cadangan Rp60 juta.
- Perbaiki tampilan negosiasi A/B/C berdampingan dan ekspor kas bulan 1–4 pada proyek utama.
- Tambahkan evaluasi kualitas terhadap rencana pembanding yang feasible, kemudian latih ulang IQL dan CTDE untuk aturan baru.
- Jalankan tes dan perbarui README, checkpoint, serta ZIP proyek.

## Keadaan sebelum pekerjaan ini

- Versi 0.8.0 / model v5; IQL dan CTDE masing-masing 20.000 episode.
- Evaluasi 500 skenario: konsensus IQL 71,0%, CTDE 72,8%; kelayakan saat itu belum menjadikan kas minimum sebagai syarat wajib.
- Vendor A/B yang lolos sudah menawar sebelum VMI memilih.
- Folder utama `C:\Users\Study\Documents\Koding\multi-agent-procurement` menyimpan riwayat SQLite pengguna. Jangan timpa database tersebut.
- Salinan kerja berada di folder `outputs\multi-agent-procurement` dalam workspace Codex. Folder utama sempat memiliki `app.py` yang berbeda dari salinan kerja; periksa ulang sebelum sinkronisasi.

## Status

- [x] Tinjau tiga CSV terbaru dan ketentuan BAB 6 pada dokumen laporan.
- [x] Implementasi syarat kas dan diagnosis. `enforce_min_cash=true` pada fixture dan generator; diagnosis mengurangi cadangan Rp60 juta dari dana belanja.
- [x] Model v6 IQL/CTDE seed 0 selesai 20.000 episode; evaluasi 500 skenario: konsensus 60,2%/64,0%, diagnosis tidak feasible 22,6%.
- [x] Pembanding terbatas 100 skenario held-out (seed 2000–2099): IQL melewatkan 4 dari 58 kasus yang pembanding temukan feasible; CTDE melewatkan 0. Selisih biaya rata-rata ketika keduanya feasible 4,13%/2,38%. Pembanding hanya satu siklus dan pembayaran deterministik.
- [x] Pelatihan seed 1 (masing-masing 20.000 episode) selesai. Konsensus IQL 59,6%, CTDE 64,0% pada 500 skenario. Checkpoint seed 0 tetap default. Pembanding seed 1 ada di `runs/quality_v6_seed1.json`.
- [x] Baseline supervised learning dilatih ulang untuk label v6: 2.042 kandidat dari 180 skenario layak; XGBoost accuracy 79,0%, F1 64,8%, ROC-AUC 0,828 pada split test per skenario. Artefak default di `runs/baseline/` sudah diperbarui.
- [x] UI dan ekspor pada salinan kerja menampilkan putaran A/B/C dan empat kolom kas; run arsip diberi peringatan aturan lama.
- [x] 19 unit test lulus; Streamlit AppTest 0 exception pada startup dan setelah membuat skenario.
- [x] Sinkronisasi 31 file aplikasi/model/dokumentasi ke proyek utama; `data/procurement.sqlite3` tidak disentuh. Di proyek utama 19 tes lulus dan Streamlit AppTest startup 0 exception.
- [x] ZIP distribusi diperbarui; memuat kode, progress.md, checkpoint v6, baseline, dan hasil evaluasi, tanpa database pengguna.

## Langkah berikutnya bila proyek dilanjutkan

- Jalankan skenario baru di Streamlit; run lama tetap arsip dan menampilkan peringatan aturan kas lama.
- Jika ingin meningkatkan kebijakan, uji lebih banyak seed pelatihan dan perluas pembanding ke termin stokastik serta perbaikan lintas siklus. Jangan menyebut hasil sekarang optimum global.
- Bila dokumen laporan mengubah asumsi kas/pendanaan, ubah fixture, naikkan versi model, lalu latih ulang IQL, CTDE, dan baseline sebelum membandingkan hasil.

## Batas interpretasi

- Pembanding kualitas hanya mencari plan **satu siklus** dengan DA terima/tawar balik dan SLM bayar cepat/jatuh tempo. Termin stokastik dan perbaikan lintas siklus tidak masuk pencarian, sehingga ini bukan optimum global.
- Skenario BAB 6 dan 600 unit tanpa pendanaan baru memang tidak feasible dengan cadangan Rp60 juta. Simulasi tidak boleh mengubahnya menjadi sukses hanya karena kas masih positif.
- Baseline supervised learning memakai data simulasi, bukan historis pengadaan perusahaan.

## Perintah verifikasi

Jalankan dari folder proyek dengan interpreter `.venv`:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts\train.py --algo iql --episodes 20000 --out runs\iql
.\.venv\Scripts\python.exe scripts\train.py --algo ctde --episodes 20000 --out runs\ctde
```

Checkpoint v6 **tidak boleh** dipakai setelah definisi reward/kelayakan berubah. Model aktif versi 7 sudah dilatih ulang.
