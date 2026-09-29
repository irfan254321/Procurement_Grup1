# Progress proyek

Dokumen ini mencatat pekerjaan aktif agar sesi berikutnya dapat melanjutkan dari keadaan terakhir. Baca file ini sebelum mengubah kode.

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

Checkpoint v5 **tidak boleh** dipakai setelah definisi reward/kelayakan berubah. Naikkan `MODEL_VERSION` dan latih ulang sebelum aplikasi menerima skenario baru.
