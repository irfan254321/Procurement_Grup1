# BIZ District

Simulasi PT. Biz Indonesia Market yang menghubungkan penjualan Laptop, Monitor, dan Printer dengan restok, negosiasi vendor, keuangan, dan penerimaan barang.

## Instalasi pertama di Windows

Siapkan **Python 3.14 64-bit**, koneksi internet untuk mengunduh dependensi, dan browser dengan WebGL 2 untuk tampilan 3D. Di GitHub, gunakan **Code → Download ZIP** atau clone repositori. Buka PowerShell di folder yang langsung berisi `electronics/`. Jika CSV katalog belum tersedia, ikuti petunjuk di bagian [Dataset dan pelatihan](#dataset-dan-pelatihan).

```powershell
py -3.14 electronics/install.py
```

Installer membuat `electronics/.venv`, memasang dependensi, mengunduh dataset pemasok Kaggle jika diperlukan, menyiapkan model, lalu menjalankan server lokal. Tunggu hingga terminal menampilkan alamat server. Jika `py -3.14` gagal menemukan Python, periksa `python --version`. Jika hasilnya Python 3.14, jalankan `python electronics/install.py`.

## Membuka kembali setelah instalasi

Jalankan server langsung dari PowerShell di folder proyek.

```powershell
.\electronics\.venv\Scripts\python.exe electronics/agent.py
```

Biarkan PowerShell terbuka selama aplikasi dipakai. Tekan **Ctrl+C** untuk menghentikan server. Jika port 8081 masih terpakai, cek terminal lama dan hentikan server di sana. Jika lingkungan Python belum ada atau dependensi di `requirements.txt` berubah, jalankan kembali perintah instalasi. [Buka BIZ District di localhost:8081](http://127.0.0.1:8081)

Jika pilihan **Otomatis · awal acak** ditolak setelah pembaruan, hentikan server yang lama, jalankan ulang perintah di atas dari folder proyek yang diperbarui, lalu muat ulang halaman.

SQLite sudah tersedia melalui Python. Saat pertama kali berjalan, server membuat `electronics/data/electronics.sqlite3` untuk menyimpan stok, kas, antrean, transaksi, pajak, dan giliran terakhir. Server memakai database yang sama saat dibuka kembali. Git mengecualikan lingkungan Python, database, hasil model `models.joblib`, dan log server.

## Menggunakan aplikasi

Gerakan agen 3D memakai jalur yang mempertimbangkan meja, kursi, rak, dan area muat. Agen memutari furnitur saat berganti tugas, masuk kantor, dan keluar kantor. Target di rak diarahkan ke sisi yang dapat dijangkau.

Saat pemasok atau pengangkut di-offline-kan, agen di ruangannya berjalan ke pintu lalu menghilang. Saat perusahaan diaktifkan, agen masuk melalui pintu dan kembali ke tempat kerja. Ruangan yang dibuka dalam kondisi offline langsung kosong. Preferensi kurangi gerakan menampilkan perubahan secara langsung.

Website pemasok dan pengangkut mengikuti tombol online/offline di distrik. Saat perusahaan ditutup, URL profil dan portalnya menampilkan halaman offline dengan desain perusahaan tersebut. Tab yang sudah terbuka memeriksa status setiap tiga detik dan memuat ulang ketika perusahaan ditutup atau diaktifkan kembali. Akses portal dibuka kembali setelah perusahaan online.

- Buka **Perusahaan online / offline** di peta 3D, atau gunakan tombol di ruang pemasok dan pengangkut. Perusahaan offline keluar dari pemilihan PO baru. Pengemasan, keberangkatan, atau koreksi faktur yang masih membutuhkan perusahaan tersebut menunggu dibuka kembali. Barang yang sudah dalam perjalanan tetap diproses.
- Klik judul perusahaan untuk membuka portal, lalu pilih **Jadwal & negosiasi**. Pada akses pertama, atur sandi minimal delapan karakter untuk perusahaan itu. Portal menyimpan jadwal negosiasi, jadwal pengiriman, dan riwayat lengkap di SQLite. Ringkasan status kiriman dan penawaran yang sedang divisualisasikan tersedia di simulasi. Reset membersihkan catatan skenario dan sesi akses, dengan sandi tetap berlaku.
- **Control Tower** memuat lima output tiap RFQ, prakiraan tiga hari dan ROP dinamis, skor pemasok, event EPCIS, anomali, dan memori agen. Nama SAP, Oracle SCM, GPS/IoT dan PostgreSQL WMS menandai sumber aliran dalam simulasi. Objek EPCIS memakai pengenal lot lokal.

- **Dunia** memakai **Otomatis · awal acak** untuk sesi baru. Server mengundi kondisi awal lalu menjalankan penjualan, restok, negosiasi, pengiriman, dan pembayaran dalam satu sesi. Pilihan kondisi khusus tersedia untuk uji ulang. Pemilihan kondisi diterapkan saat **Mulai ulang skenario**. Klik lantai atau gedung vendor untuk melihat aktivitasnya.
- **Lobi dan toko** menampilkan antrean pelayanan, etalase Laptop, Monitor, dan Printer, harga termasuk PPN, serta stok yang tersedia. Transaksi yang kekurangan stok langsung ditutup dan tercatat di **Hasil terakhir**. Pembelian baru bisa diproses setelah barang diterima dan masuk stok jual.
- **Laba perusahaan** menampilkan grafik pendapatan, laba kotor, dan saldo kas, serta rincian faktur vendor, penjualan, dan posisi pajak.
- **Model agen** menampilkan metrik validasi dan pengujian serta model pilihan tiap agen.
- **Pasokan & pengiriman** menampilkan stok tiap vendor, kapasitas tersedia, skor risiko setelah penawaran, serta jumlah, rute, tenggat, dan faktur per kiriman. Gunakan **+**, **−**, atau **Lihat semua** untuk mengatur peta 3D.
- Klik lantai BIZ, gedung pemasok, atau terminal pengangkut untuk membuka **Profil**, **Aturan**, dan **Biaya logistik** perusahaan. Biaya logistik merangkum ongkir pada faktur terbuka dan dibayar. Kalkulator dapat membandingkan estimasi biaya tetap dan biaya per unit untuk sebuah kiriman.
- Klik **nama perusahaan** di dalam gedung untuk langsung membuka profilnya. Setiap perusahaan punya desain sendiri, seperti [TechMart](http://127.0.0.1:8081/techmart/), [BIZ](http://127.0.0.1:8081/biz/), dan [J&T Cargo](http://127.0.0.1:8081/jt-cargo/). Dari profil, buka **Aturan** atau **Biaya logistik** untuk melihat data perusahaan, termasuk rute dan jarak simulasi yang memengaruhi ongkir.

Tombol **Mulai ulang skenario** mengembalikan stok, kas, riwayat, dan pencatatan pajak lokal ke kondisi awal skenario terpilih.

### Mencoba skenario barang rusak

1. Di tab **Dunia**, pilih **Barang rusak → koreksi faktur**.
2. Klik **Mulai ulang skenario** dan ikuti aktivitas gudang, vendor, dan keuangan. Gunakan **Jeda** dan **Giliran berikutnya** untuk melihat tiap keputusan.
3. Buka **Laba perusahaan** untuk membandingkan faktur awal dengan faktur setelah koreksi, serta jumlah barang layak jual dan rusak.

### Mencoba lonjakan permintaan dan penurunan kapasitas

1. Pilih **Permintaan naik → pasokan terbatas** di tab **Dunia**, lalu klik **Mulai ulang skenario**.
2. BIZ membutuhkan 30 Laptop dengan tenggat empat hari simulasi. Kapasitas vendor pertama, CloudSoft Corp., turun dari 7 menjadi 4 unit per periode. Buka gedung vendor untuk melihat stok dan sisa kapasitasnya.
3. Pantau **Pasokan & pengiriman**. Pengadaan mengalokasikan kebutuhan ke beberapa vendor dan memilih layanan pengiriman. Setelah pemasok mengemas pesanan, kendaraan berangkat dari terminal pengangkut, berhenti menjemput barang di vendor, lalu mengantar ke Gudang BIZ. Gudang memproses kiriman menurut urutan jadwal kedatangan. Keuangan mencocokkan dan membayar setiap faktur.

Pengangkut yang dapat dipilih adalah [JNE](https://www.jne.co.id/jtr-id), [J&T Cargo](https://www.jtcargo.id/serviceProducts), dan [Pos Logistik Indonesia](https://admin-piol.posindonesia.co.id/media/AR%20POS%202024%20HiRes.pdf). Kapasitas per kiriman, ongkir, rute, dan jadwal yang terlihat di aplikasi adalah parameter simulasi. Rujukan resmi digunakan untuk identitas dan profil perusahaan.

## Alur simulasi dan model

Modul keputusan ada di `agents/`, penyimpanan dan kontrol akses di `database/`, pembacaan sumber data di `datasets/`, pelatihan di `training/`, dan konfigurasi lokasi di `paths.py`. Perintah pelatihan lama tetap tersedia dari folder utama proyek.

Memori agen merekam keputusan dan fakta dari state transaksi yang sama. Gunakan `GET /api/memory` atau `GET /api/memory/<role>` untuk membacanya. Uji Python dapat dijalankan dengan `python -m unittest discover -s electronics/tests`, dan uji frontend dengan `node electronics/tests/check-3d-integration.cjs`.

Browser meminta giliran berikutnya lewat API. Server Python menjalankan agen yang bertugas, menerapkan aturan bisnis, menyimpan kondisi ke SQLite, lalu mengirim hasil untuk ditampilkan di distrik 3D.

| Agen | Model utama | Peran |
| --- | --- | --- |
| Pembeli | CatBoost | Menilai minat beli dari harga, anggaran, dan jumlah pesanan. |
| Penjual | Random Forest | Menilai apakah pelanggan dapat dilayani dengan stok yang tersedia. |
| Stock | Logistic Regression | Memperkirakan kebutuhan restok dari stok, permintaan tercatat, dan titik pesan. |
| Pengadaan | SVM | Memprioritaskan vendor untuk dimintai penawaran. |
| Vendor | Gradient Boosting | Menilai tawaran berdasarkan batas harga dan kapasitas. |
| Negosiasi | KNN | Menilai apakah tawaran dapat disepakati. |
| Keuangan | XGBoost | Memprediksi kelayakan pembelian. Keputusan akhir mengikuti aturan kas, anggaran, dan proyeksi laba. |

Saat stok rendah atau kebutuhan mendatang diperkirakan melebihi persediaan, agen Stock mengajukan restok. Jika dana kurang, permintaan tetap tersimpan dan toko melayani penjualan dari stok yang tersedia. Dana pengadaan diisi kembali dari modal barang yang terjual dan 50% laba kotor positif. Saat kas bebas dan anggaran cukup untuk melanjutkan, Pengadaan memproses permintaan yang tertahan.

Pengadaan membandingkan penawaran empat pemasok. Tiap pemasok mendapat hingga tiga putaran tawar balik dan dapat menawarkan sebagian dari kebutuhan. Sebelum persetujuan keuangan, fase penawaran ekspedisi memperlihatkan pilihan layanan tiga pengangkut dan menandai layanan terpilih. Pengalokasi memeriksa tenggat, stok, kapasitas, anggaran, dan target laba. Biaya yang dibandingkan meliputi barang, ongkir tetap/per unit, PPN simulasi, dan penalti biaya barang × skor risiko × 0,15.

Stok dan kapasitas vendor disimpan di SQLite. Saat pesanan disetujui, stok dan kapasitasnya berkurang. Setiap 24 giliran kapasitas terisi kembali dan stok bertambah sampai batas simulasi. Rute memakai graf distrik dengan terminal pengangkut sebagai bagian perjalanan. Layanan ekspres memakai koridor selatan, dengan ongkir dan waktu tempuh yang berbeda dari layanan reguler. Hari simulasi mengikuti kedatangan, sedangkan giliran memajukan langkah kerja agen.

Keuangan mencadangkan total semua faktur yang disetujui. Tiap pembayaran kemudian mengurangi kas dan melepas cadangan faktur tersebut. Saat barang rusak, faktur mengurangi nilai barang yang tidak lolos penerimaan. Ongkir tetap menjadi biaya kiriman.

Pada uji barang rusak, dua unit pada kiriman pertama dipisahkan untuk retur. Mode otomatis juga dapat memunculkan barang rusak pada kiriman lain. Keuangan menahan pembayaran sampai vendor menerbitkan faktur pengganti. Kas dan PPN masukan dicatat berdasarkan faktur pengganti, lalu selisih dana dikembalikan ke anggaran pengadaan.

## Dataset dan pelatihan

CSV `spend_analysis_dataset.csv` memberi acuan produk, vendor, dan harga dari 146 transaksi elektronik dalam 500 baris. Jika CSV belum ada di salinan repositori, unduh arsip sumber dan ekstrak berkas CSV ke `electronics/data/spend_analysis_dataset.csv`. [Company Purchasing Dataset oleh Shahriar Kabir di Kaggle](https://www.kaggle.com/datasets/shahriarkabir/company-purchasing-dataset)

Dataset tambahan [Supply Chain Shipment Pricing Data di Kaggle](https://www.kaggle.com/datasets/divyeshardeshana/supply-chain-shipment-pricing-data) melatih CatBoost untuk memberi skor keterlambatan pemasok. Jadwal di simulator mengikuti jadwal historis yang dikonversi ke hari simulasi. Pada validasi, jadwal acuan menghasilkan galat lebih rendah daripada model regresi. Lihat [sumber, pembagian data, dan hasil uji pemasok](data/supplier/README.md).

Skenario barang rusak menggunakan aturan simulasi. Untuk melatih prediksi risiko kerusakan, gunakan data pemeriksaan penerimaan yang mencakup kiriman layak dan rusak, dengan produk, vendor, pengangkut, jumlah, dan kondisi barang.

Pelatihan membagi riwayat elektronik secara kronologis menjadi 100 baris latih, 23 validasi, dan 23 uji. Dari setiap bagian, `train.py` membuat 1.600 contoh berlabel per agen dengan seed berbeda. Label stok memakai stok setelah memenuhi permintaan. Label keuangan membandingkan dana tersedia dengan faktur termasuk PPN dan memeriksa proyeksi laba kotor. Sembilan algoritme dibandingkan. Model utama dipilih berdasarkan akurasi seimbang validasi dengan syarat berbeda antartujuh agen. Empat model cadangan disimpan per agen. Akurasi uji mengukur kesesuaian prediksi dengan aturan pemberian label.

Hasil pelatihan disimpan di `data/models.joblib` dan `data/metrics.json`. Untuk melatih ulang di Windows setelah instalasi, hentikan server dan jalankan dari root repositori.

```powershell
.\electronics\.venv\Scripts\python.exe electronics/train.py
```

## Kas dan pajak

Satu satuan dataset setara Rp10.000 di simulasi. Faktur vendor menampilkan harga dasar, PPN masukan, dan total pembelian. Penjualan mencatat PPN keluaran serta pendapatan sebelum PPN. Laba kotor adalah pendapatan dikurangi harga pokok penjualan.

PPN efektif 11% berlaku untuk skenario barang elektronik domestik nonmewah, dengan asumsi BIZ dan vendor berstatus PKP dan faktur masukan memenuhi syarat pengkreditan. Dashboard mencatat saldo PPN kumulatif sejak fitur aktif. [Ketentuan PPN DJP](https://pajak.go.id/id/peraturan/perlakuan-pajak-pertambahan-nilai-atas-impor-barang-kena-pajak-penyerahan-barang-kena)

Masukkan nominal PBB-P2 berdasarkan SPPT, atau nominal PPh Badan, PPh 21, PPh 23, dan Bea Meterai melalui formulir tagihan. **Catat setoran** mengurangi kas dan mencatat pembayaran di simulasi lokal. [Buku elektronik DJP](https://pajak.go.id/id/buku-elektronik-page)

## Aset 3D

Three.js merender distrik, animasi agen, dan interior di browser. Model Poly Pizza untuk gedung vendor, truk, sofa, laptop, monitor, dan printer dimuat dari berkas GLB lokal. Nama pembuat, sumber, dan lisensi tercantum di [kredit aset](web/assets/CREDITS.md).

## Struktur folder

| Lokasi | Isi |
| --- | --- |
| `install.py` | Instalasi lokal, penyiapan model, dan peluncuran server |
| `agent.py` | API, giliran simulasi, dan penyimpanan SQLite |
| `domain.py`, `train.py` | Katalog, aturan label, pelatihan, dan evaluasi model |
| `supply_chain.py` | Stok vendor, pemilihan rute, dan pembagian pesanan |
| `supplier_data.py`, `supplier_training.py` | Profil pemasok, pelatihan, dan prediksi keterlambatan |
| `finance.py` | Pencatatan kas, grafik, dan pembayaran pajak |
| `web/` | Antarmuka, Three.js, dan aset 3D |
| `data/` | CSV sumber, metrik, model, dan database lokal |
| `tests/` | Tes alur penerimaan, pembayaran, dan integrasi tampilan 3D |

## Pengujian

Setelah instalasi, jalankan tes penerimaan dan koreksi faktur dari folder proyek.

```powershell
.\electronics\.venv\Scripts\python.exe -m unittest discover -s electronics/tests -v
```

Untuk menjalankan tes tampilan 3D, gunakan Node.js dari folder yang sama.

```powershell
node electronics/tests/check-3d-integration.cjs
```
