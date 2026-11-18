# Dataset pemasok SCMS

Sumber tambahan adalah [Supply Chain Shipment Pricing Data di Kaggle](https://www.kaggle.com/datasets/divyeshardeshana/supply-chain-shipment-pricing-data). [Katalog sumber USAID](https://data.amerigeoss.org/dataset/supply-chain-shipment-pricing-data) menerangkan bahwa dataset mencatat kiriman komoditas kesehatan. Salinan Kaggle menyebut lisensi `Unknown`. Katalog sumber mencantumkan CC BY-ND 4.0 dan atribusi penerbit. Pengunduh menyimpan salinan CSV tanpa modifikasi dan memeriksa checksum. CSV, model, dan manifest hasil pembagian disimpan lokal.

```powershell
.\electronics\.venv\Scripts\python.exe electronics/download_supplier_data.py
.\electronics\.venv\Scripts\python.exe electronics/supplier_training.py --ensure
```

Dari 10.324 baris, 4.587 memiliki tanggal yang memenuhi syarat. Baris dikelompokkan menurut pesanan pembelian lalu dibagi secara kronologis. Setelah mengeluarkan hasil pengiriman yang belum tersedia pada awal periode berikutnya, tersisa 2.624 baris latih, 503 validasi, dan 1.149 uji. Label terlambat berasal dari tanggal tiba aktual yang melewati tanggal terjadwal. Model menerima tanggal rencana, konteks vendor, moda, jumlah, dan fitur lain yang tersedia sebelum keputusan. Tanggal tiba aktual hanya membentuk label.

CatBoost mencapai balanced accuracy 67,92%, ROC-AUC 63,46%, precision 8,85%, dan recall 51,52% pada uji historis. Hanya 33 dari 1.149 baris uji terlambat. Jadwal acuan dipilih untuk waktu kirim berdasarkan galat validasi. Rinciannya ada di `metrics.json` dan tab **Model agen**.

Lima vendor elektronik dipetakan ke profil historis untuk kepentingan simulasi. Stok, kapasitas, ongkir, dan graf rute ditentukan oleh skenario. Durasi memakai satu hari simulasi per 30 hari historis, dengan faktor 0,75 untuk ekspres dan minimum satu hari. Skor model memengaruhi pemilihan alokasi dan belum dikalibrasi atau divalidasi pada distribusi elektronik.
