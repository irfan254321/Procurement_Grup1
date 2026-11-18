# BIZ District

Aplikasi utama proyek ini berada di **[`electronics/`](electronics/README.md)**: simulasi penjualan Laptop, Monitor, dan Printer, restok, negosiasi vendor, keuangan, penerimaan barang, serta tampilan distrik 3D.

## Instalasi dan menjalankan aplikasi

Gunakan Python **3.14 64-bit**. Jalankan dari folder utama repositori:

```powershell
py -3.14 electronics/install.py
```

Installer membuat lingkungan Python di `electronics/.venv`, memasang dependensi, menyiapkan model, lalu menjalankan server. Buka [BIZ District](http://127.0.0.1:8081) setelah alamat server muncul di terminal.

Untuk membuka kembali aplikasi setelah instalasi:

```powershell
.\electronics\.venv\Scripts\python.exe electronics/server.py
```

Tekan **Ctrl+C** di terminal untuk menghentikan server.

## Struktur proyek

| Lokasi | Fungsi |
| --- | --- |
| `electronics/server.py` | Server lokal, API, dan alur simulasi |
| `electronics/domain.py`, `electronics/finance.py` | Katalog, aturan agen, dan keuangan |
| `electronics/train.py` | Pelatihan dan evaluasi model agen |
| `electronics/install.py`, `electronics/requirements.txt` | Instalasi dan dependensi aplikasi |
| `electronics/web/` | Antarmuka dan aset 3D |
| `electronics/data/` | Dataset, metrik, model, dan database lokal |
| `electronics/tests/` | Pengujian alur simulasi dan integrasi tampilan |

Data simulasi disimpan di `electronics/data/electronics.sqlite3`. Model, database, dan lingkungan Python lokal dikecualikan dari Git; installer menyiapkan model jika belum tersedia.

## Pengujian

Jalankan dari folder utama repositori setelah instalasi:

```powershell
.\electronics\.venv\Scripts\python.exe -m unittest discover -s electronics/tests -p test_receiving.py -v
node electronics/tests/check-3d-integration.cjs
```

Panduan penggunaan, dataset, pelatihan ulang, dan kredit aset tersedia di [panduan lengkap electronics](electronics/README.md).
