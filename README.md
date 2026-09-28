# Multi-Agent Procurement Simulator

Dashboard Streamlit untuk empat agen **IRE, VMI, DA, SLM** dengan dua pilihan kebijakan yang benar-benar dilatih: **Independent Q-learning (IQL)** dan **CTDE actor-critic**. Sesuai bagian *Algorithm and AI Integration* pada laporan, proyek juga melatih **Logistic Regression, SVM, Random Forest, dan XGBoost** sebagai baseline supervised learning. Setiap skenario selesai otomatis, lalu tindakan agen dapat ditelusuri langkah demi langkah. Rencana dan laporan singkat disimpan di SQLite.

## Jalankan aplikasi

Proyek menggunakan Python **3.14** (versi yang dipakai untuk pelatihan dan pengujian saat ini). Dari folder proyek:

**Windows PowerShell**

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -e . --no-deps
python -m unittest discover -s tests -v
streamlit run app.py
```

**macOS/Linux** (gunakan interpreter Python 3.14 yang tersedia)

```bash
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install -e . --no-deps
python -m unittest discover -s tests -v
streamlit run app.py
```

Checkpoint terlatih disertakan di `runs/iql/` dan `runs/ctde/`. Aplikasi tidak melatih ulang saat pengguna menekan **Buat & jalankan skenario**. Untuk melatih ulang:

```bash
python scripts/train.py --algo iql --episodes 50000 --out runs/iql
python scripts/train.py --algo ctde --episodes 50000 --out runs/ctde
python scripts/train_baseline.py --scenarios 300 --seed 42 --out runs/baseline
```

Setiap pelatihan menulis kurva `curve.csv`, parameter `config.json`, dan checkpoint. Latih ulang sebelum mengganti definisi observasi, aksi, atau reward.

Paket `procurement_marl` berada di folder `src/`. Instalasi editable (`pip install -e . --no-deps`) membuatnya dapat diimpor oleh interpreter virtual environment; `pyrightconfig.json` memberi tahu editor lokasi sumbernya. Jika editor masih menandai impor merah, pilih interpreter `.venv/Scripts/python.exe` (Windows) atau `.venv/bin/python` (macOS), lalu muat ulang editor.

Hasil evaluasi setelah 50.000 episode latihan, pada 500 skenario yang sama (seed evaluasi 0–499, seed latihan 0):

| Model | Return tim | Konsensus | Terdeteksi tidak feasible | Minta revisi | Revisi keliru |
|---|---:|---:|---:|---:|---:|
| IQL | 15,64 | 68,8% | 20,8% | 19,8% | 0,0% |
| CTDE | 18,30 | 70,2% | 20,8% | 26,4% | 5,6% |

Sekitar 20% generator latihan sengaja membuat kasus kekurangan dana yang dapat dibuktikan. Konsensus dan tidak feasible adalah hasil yang berbeda, sehingga keduanya tidak dijumlahkan sebagai “tingkat sukses”. CTDE memperoleh return dan konsensus lebih tinggi, tetapi juga lebih sering meminta revisi terlalu dini. Ini evaluasi satu seed pelatihan; jangan menganggap selisih kecil sebagai bukti umum bahwa satu algoritma selalu lebih unggul. Kasus BAB 6 ditolak sebagai **TIDAK FEASIBLE** oleh kedua model.

### Evaluasi baseline supervised learning

Proyek tidak menerima dataset historis perusahaan bersama laporan. Agar bagian algoritma dapat dijalankan tanpa mengaku memakai data riil, `scripts/train_baseline.py` membuat kandidat keputusan dari simulator dan memberi label memakai oracle: **optimal** berarti rencana layak dan biayanya maksimal 3% di atas biaya layak terendah pada skenario yang sama. Split 80/20 dilakukan berdasarkan ID skenario, sehingga kandidat dari skenario test tidak muncul di train.

Hasil artefak yang disertakan, dari 2.199 keputusan pada 193 skenario yang mempunyai solusi layak:

| Model | Accuracy | Precision | Recall | F1 | ROC-AUC |
|---|---:|---:|---:|---:|---:|
| Logistic Regression | 79,0% | 56,9% | 81,9% | 67,1% | 0,869 |
| SVM | 81,7% | 68,8% | 55,2% | 61,2% | 0,855 |
| Random Forest | 81,0% | 63,3% | 65,5% | 64,4% | 0,877 |
| XGBoost | **83,7%** | **72,0%** | 62,1% | 66,7% | **0,890** |

XGBoost dipakai sebagai pembanding utama karena accuracy dan ROC-AUC test tertinggi. Logistic Regression mempunyai recall dan F1 sedikit lebih tinggi; tabel lengkap serta confusion matrix tetap ditampilkan agar trade-off terlihat. Angka ini hanya berlaku pada data simulasi. Untuk klaim performa dunia nyata, latih ulang dengan data historis organisasi dan validasi periode waktu yang belum pernah dilihat model.

## Penggunaan

1. Pilih **CTDE** atau **IQL**.
2. Isi **jumlah unit, unit mendesak, dan anggaran**. Nilai awal mereproduksi permintaan BAB 6. Tenggat, kas, kewajiban, dan profil vendor memakai acuan laporan.
3. Klik **Buat & jalankan skenario**. Model memilih aksi untuk keempat agen secara otomatis. Seed yang sama menghasilkan respons vendor yang dapat diulang.
4. Di **Proses agen**, gunakan **Maju/Mundur** untuk melihat VMI memeriksa A, B, dan C satu per satu. Status tabel bergerak dari belum diperiksa, sedang diperiksa, lolos/gagal, sampai vendor dipilih, dinegosiasikan, dan diberi rencana pembayaran.
5. Di **Pelaporan**, lihat status akhir, biaya, kendala, klasifikasi XGBoost, tabel evaluasi empat baseline, grafik kas akhir, dan jejak lengkap dalam panel terlipat. Laporan serta audit CSV dapat diunduh dan otomatis tersimpan di `data/procurement.sqlite3`.
6. Di **Konfigurasi vendor**, edit data A/B/C lalu pilih **Terapkan untuk skenario berikutnya**. Tombol **Kembalikan data BAB 6** menghapus konfigurasi khusus.

Harga awal, kapasitas, diskon, dan lead time vendor berasal dari data skenario. DA dapat memilih penawaran awal, tawaran balik, atau alternatif vendor. SLM dapat memilih pembayaran cepat, jatuh tempo, revisi termin, atau meminta revisi skenario. Respons vendor pada tawaran balik/termin disimulasikan dari peluang dan relasi yang tercatat, bukan diacak ulang setiap kali halaman dibuka. Tidak ada integrasi portal vendor atau pembayaran ERP; semuanya rekomendasi simulasi.

Konfigurasi vendor aktif disimpan di tabel SQLite `vendor_settings`. Setiap run tetap menyimpan snapshot vendornya sendiri, sehingga mengedit vendor tidak mengubah hasil yang sudah ada. Jumlah vendor tetap tiga agar action space checkpoint IQL dan CTDE tetap cocok. Perubahan nilai yang sangat jauh dari rentang latihan harus diperlakukan sebagai eksperimen terhadap model.

Status hasil dibedakan menjadi **LAYAK**, **PERLU REVISI**, dan **TIDAK FEASIBLE**. Status terakhir hanya dipakai ketika batas bawah biaya sudah melampaui seluruh dana yang tersedia. Penjelasan alur lengkap untuk mahasiswa tersedia di [`docs/ALUR_KODE.md`](docs/ALUR_KODE.md).

## Hubungan dengan laporan

- [config/report_scenario.yaml](config/report_scenario.yaml) memuat A/B/C dan asumsi keuangan BAB 6. Dengan tindakan contoh laporan, pengadaan awal B berbiaya **Rp99.710.000** dengan defisit kas **Rp19.710.000**. Usulan 700 B + 300 A berbiaya **Rp100.397.000**, masih melanggar anggaran dan kas. Tes legacy menjaga angka tersebut.
- **Kebijakan terlatih boleh mengambil tindakan berbeda** dari jejak contoh BAB 6. Kelayakan tetap ditentukan oleh pemeriksaan anggaran, kas, kapasitas, skor vendor, dan kebutuhan mendesak oleh environment. Return reward yang tinggi tidak otomatis berarti rencana layak.
- Dokumen merancang CTDE dengan critic terpusat dan shared replay buffer. Implementasi di sini memiliki actor lokal per agen, satu critic state gabungan, dan shared replay buffer untuk melatih critic. Pembaruan actor memakai episode baru. IQL mempunyai Q-table terpisah per agen. Detail ada di `src/procurement_marl/agents/`.
- Logistic Regression, SVM, Random Forest, dan XGBoost adalah **baseline klasifikasi keputusan**, bukan agen tambahan. Baseline membaca rencana setelah MARL selesai dan tidak dapat mengubah hasil evaluator.
- Karena dataset historis yang disebut laporan tidak tersedia, artefak bawaan memakai dataset simulasi di `runs/baseline/dataset_simulasi.csv`. Keterangan sumber data juga tampil di dashboard.
- Angka reward −10 dan +150 pada laporan hanya ilustrasi, bukan reward hasil pelatihan. Fungsi reward simulator didokumentasikan di [config/env_default.yaml](config/env_default.yaml) dan `src/procurement_marl/rewards.py`.

## Struktur penting

```text
app.py                                UI proses dan Pelaporan
procurement/rl_service.py             input 3 variabel, muat model, jalankan episode
procurement/rl_storage.py             simpan log dan laporan SQLite
procurement/baseline_ml.py             fitur dan inferensi baseline supervised learning
src/procurement_marl/env.py           giliran agen, negosiasi, pembayaran, kendala
src/procurement_marl/scenario.py      vendor, fixture, dan generator skenario latihan
src/procurement_marl/agents/iql.py    pembaruan Q-table IQL
src/procurement_marl/agents/ctde_ac.py actor-critic CTDE + shared critic replay
src/procurement_marl/costs.py         perhitungan biaya dan kas
config/                               data laporan dan asumsi latihan
scripts/train.py                      latihan model
scripts/train_baseline.py             dataset, train/test, dan evaluasi empat classifier
runs/                                 checkpoint dan kurva hasil latihan
tests/                                tes biaya, model, dan penyimpanan
```

Modul `procurement/models.py`, `workflow.py`, dan `simulator.py` dari versi rule-based lama masih disimpan untuk contoh perhitungan dan kompatibilitas tes; dashboard terbaru memakai `procurement/rl_service.py` dan `src/procurement_marl/`.

## Git

`.gitignore` mengecualikan virtual environment, cache Python, dan database lokal. Checkpoint terlatih dalam `runs/` perlu ikut disimpan bila dashboard ingin langsung dijalankan tanpa latihan ulang.

```bash
git init
git add .
git commit -m "Add trained IQL and CTDE procurement agents"
```
