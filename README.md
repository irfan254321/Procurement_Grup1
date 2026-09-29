# Multi-Agent Procurement Simulator

Untuk belajar kode per file, baca [panduan semua file Python](docs/PANDUAN_FILE_PYTHON.md). Komentar berbahasa Indonesia di setiap modul menjelaskan perannya; panduan tersebut menjelaskan sintaks penting dan urutan membaca proyek.

Panduan percobaan dengan input, tujuan, dan hasil nyata tersedia di [20 skenario uji](docs/20_skenario_uji.md). Jalankan `python scripts/run_demo_scenarios.py` untuk mengulang semuanya ke JSON tanpa mengubah database riwayat aplikasi.

Dashboard Streamlit untuk empat agen **IRE, VMI, DA, SLM** dengan dua pilihan kebijakan yang benar-benar dilatih: **Independent Q-learning (IQL)** dan **CTDE actor-critic**. Vendor A/B/C mempunyai agen negosiasi berbasis utilitas. Setiap vendor yang lolos penyaringan merespons permintaan harga yang sama sebelum VMI memilih pemasok. Penawaran pembeli dan balasan vendor terlihat berdampingan per putaran. DA lalu menerima harga kandidat, menawar lagi, atau meminta vendor alternatif; SLM memeriksa termin dan kas. Vendor tidak menawar di bawah harga minimum masing-masing. Sesuai bagian *Algorithm and AI Integration* pada laporan, proyek juga melatih **Logistic Regression, SVM, Random Forest, dan XGBoost** sebagai baseline supervised learning.

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
python scripts/train.py --algo iql --episodes 20000 --out runs/iql
python scripts/train.py --algo ctde --episodes 20000 --out runs/ctde
python scripts/train_baseline.py --scenarios 300 --seed 42 --out runs/baseline
```

Setiap pelatihan menulis kurva `curve.csv`, parameter `config.json`, dan checkpoint. Latih ulang sebelum mengganti definisi observasi, aksi, atau reward.

Paket `procurement_marl` berada di folder `src/`. Instalasi editable (`pip install -e . --no-deps`) membuatnya dapat diimpor oleh interpreter virtual environment; `pyrightconfig.json` memberi tahu editor lokasi sumbernya. Jika editor masih menandai impor merah, pilih interpreter `.venv/Scripts/python.exe` (Windows) atau `.venv/bin/python` (macOS), lalu muat ulang editor.

Mulai versi 0.10.0, target kas Rp60 juta kembali menjadi **peringatan**, sesuai pilihan pengguna. Rencana dengan kas positif di bawah target dapat berstatus LAYAK jika anggaran, kapasitas, tenggat, dan syarat lain terpenuhi. Kas negatif tetap tidak layak. Pada fixture BAB 6, dana yang tersedia untuk belanja adalah Rp150 juta dikurangi kewajiban lain Rp70 juta, yaitu Rp80 juta; target Rp60 juta dilaporkan terpisah. Run lama tetap tersimpan, tetapi statusnya tidak dinilai ulang otomatis.

Hasil evaluasi model versi 7 setelah 20.000 episode latihan, pada 500 skenario yang sama (seed evaluasi 0–499, seed latihan 0):

| Model | Return tim | Konsensus | Terdeteksi tidak feasible | Minta revisi | Revisi keliru |
|---|---:|---:|---:|---:|---:|
| IQL | 17,60 | 71,0% | 20,8% | 20,4% | 0,0% |
| CTDE | 20,22 | 72,8% | 20,8% | 25,8% | 5,0% |

Sekitar 20% generator latihan sengaja membuat kasus kekurangan dana yang dapat dibuktikan; pada 500 skenario evaluasi angka nyatanya 20,8%. Konsensus dan tidak feasible adalah hasil yang berbeda. Kasus awal BAB 6 tetap ditolak oleh kedua model karena kekurangan dana total, walaupun target kas minimum hanya peringatan.

`scripts/evaluate_quality.py` membandingkan model dengan pencarian seluruh kandidat **satu siklus** yang menggunakan DA terima/tawar balik serta SLM bayar cepat/jatuh tempo. Ini pembanding yang dapat diaudit, bukan bukti optimum global karena revisi termin stokastik dan perbaikan lintas siklus tidak dicakup. Pada 100 skenario terpisah (seed 2000–2099), pembanding menemukan 76 kasus feasible: IQL melewatkan 2, CTDE melewatkan 0. Saat model dan pembanding sama-sama feasible, biaya model rata-rata di atas pembanding sebesar 3,45% (IQL; 74 kasus) dan 2,32% (CTDE; 76 kasus).

Checkpoint aplikasi memakai seed pelatihan 0. Artefak seed 1 dari versi 6 disimpan sebagai arsip dan **tidak boleh** dipakai dengan aturan versi 7. Angka evaluasi satu seed belum cukup untuk mengklaim optimum global.

### Evaluasi baseline supervised learning

Proyek tidak menerima dataset historis perusahaan bersama laporan. Agar bagian algoritma dapat dijalankan tanpa mengaku memakai data riil, `scripts/train_baseline.py` membuat kandidat keputusan dari simulator: **optimal** berarti rencana layak dan biayanya maksimal 3% di atas biaya layak terendah dari kandidat yang dievaluasi pada skenario yang sama. Split 80/20 dilakukan berdasarkan ID skenario, sehingga kandidat dari skenario test tidak muncul di train.

Hasil artefak yang dilatih ulang untuk aturan kas v7, dari 2.180 keputusan pada 199 skenario yang mempunyai kandidat solusi layak:

| Model | Accuracy | Precision | Recall | F1 | ROC-AUC |
|---|---:|---:|---:|---:|---:|
| Logistic Regression | 70,9% | 48,6% | **72,5%** | 58,2% | 0,821 |
| SVM | 78,6% | **65,2%** | 50,0% | 56,6% | 0,840 |
| Random Forest | 75,3% | 54,5% | 70,8% | 61,6% | 0,835 |
| XGBoost | **79,7%** | 62,8% | 67,5% | **65,1%** | **0,842** |

XGBoost dipakai sebagai pembanding utama karena accuracy, F1, dan ROC-AUC test tertinggi. Logistic Regression mempunyai recall tertinggi, sedangkan SVM mempunyai precision tertinggi. Tabel lengkap serta confusion matrix tetap ditampilkan agar trade-off terlihat. Angka ini hanya berlaku pada data simulasi.

## Penggunaan

1. Pilih **CTDE** atau **IQL**.
2. Isi **jumlah unit, unit mendesak, dan anggaran**. Nilai awal mereproduksi permintaan BAB 6. Tenggat, kas, kewajiban, dan profil vendor memakai acuan laporan.
3. Klik **Buat & jalankan skenario**. Model memilih aksi untuk keempat agen secara otomatis. Seed yang sama menghasilkan respons vendor yang dapat diulang.
4. Di **Proses agen**, gunakan **Maju/Mundur** untuk melihat VMI memeriksa A, B, dan C satu per satu. Status tabel bergerak dari belum diperiksa, sedang diperiksa, lolos/gagal, sampai vendor dipilih, dinegosiasikan, dan diberi rencana pembayaran.
5. Di **Pelaporan**, lihat status akhir, biaya, kendala, klasifikasi XGBoost, tabel evaluasi empat baseline, grafik kas akhir, dan jejak lengkap dalam panel terlipat. Laporan serta audit CSV dapat diunduh dan otomatis tersimpan di `data/procurement.sqlite3`.
6. Di **Konfigurasi vendor**, edit data A/B/C lalu pilih **Terapkan untuk skenario berikutnya**. Tombol **Kembalikan data BAB 6** menghapus konfigurasi khusus.

Harga awal, kapasitas, diskon, dan lead time vendor berasal dari data skenario. DA dapat memilih penawaran awal, tawaran balik, atau alternatif vendor. SLM dapat memilih pembayaran cepat, jatuh tempo, revisi termin, atau meminta revisi skenario. Harga balasan dihitung oleh utilitas vendor; respons termin memakai peluang yang berasal dari utilitas serta seed. Halaman tidak mengacak ulang hasil yang sudah disimpan. Tidak ada integrasi portal vendor atau pembayaran ERP; semuanya rekomendasi simulasi.

Saat DA menawar balik, agen vendor menjalankan maksimal tiga ronde internal. Harga reservasi dihitung dari harga minimum, tekanan kapasitas, relasi, jumlah pesaing, besar pesanan, dan karakter vendor. Vendor A moderat, B lebih tegas saat kapasitas terpakai, dan C lebih cepat memberi konsesi. Seed memengaruhi respons termin yang probabilistik; harga tidak pernah turun di bawah `floor_price`. Vendor ini berbasis utilitas dan tidak diklaim sebagai model reinforcement learning.

Harga minimum bawaan memberi ruang negosiasi yang terlihat: A Rp90.000, B Rp86.500, dan C Rp101.000. Penawaran awal laporan tetap A Rp95.000, B Rp89.500, dan C Rp110.000. Karena harga minimum merupakan asumsi simulator, rekonstruksi transaksi awal BAB 6 tetap memakai penawaran awal dan tidak berubah.

Jika DA meminta vendor alternatif tetapi biaya vendor pengganti tidak lebih rendah, DA mendapat penalti kecil −0,35. Saat tawaran pembeli mencapai harga vendor, kesepakatan dicatat termasuk bila harga awal sama dengan harga minimum. Jejak audit CSV menampilkan kas bulan 1–4. Respons termin menampilkan utilitas, peluang menerima, dan angka acak dari seed agar keputusan probabilistik dapat diperiksa.

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
src/procurement_marl/vendor_agents.py utilitas dan respons otonom Vendor A/B/C
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
