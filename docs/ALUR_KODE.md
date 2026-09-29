# Alur Kode dan Cara Membacanya

Dokumen ini menjelaskan hubungan antarfail untuk mahasiswa. Dashboard menjalankan satu episode simulasi secara otomatis, lalu menyimpan hasilnya agar pengguna dapat membaca ulang setiap keputusan.

## 1. Dari input sampai laporan

```text
Input pengguna di app.py
        ↓
scenario_from_request()
        ↓
Muat checkpoint IQL atau CTDE
        ↓
ProcurementEnv.reset()
        ↓
IRE → saring vendor → A/B/C saling memberi penawaran → VMI → DA → SLM → Evaluator Sistem
        ↓
Ulangi bila masih dapat diperbaiki
        ↓
LAYAK / PERLU REVISI / TIDAK FEASIBLE
        ↓
save_run() menyimpan skenario, laporan, dan semua event ke SQLite
        ↓
Tab Proses membaca ulang event; tab Pelaporan merangkum hasil akhir
        ↓
Baseline LR/SVM/RF/XGBoost menilai rencana yang sudah selesai
```

Pengguna hanya mengisi jumlah unit, unit mendesak, anggaran, metode, dan seed. Profil vendor, tenggat, kas awal, kewajiban, serta arus kas diambil dari fixture BAB 6. Karena itu pengguna tidak perlu menulis negosiasi vendor satu per satu.

## 2. Tanggung jawab setiap agen

### IRE

IRE menentukan waktu pemenuhan kebutuhan:

- satu batch pada bulan pertama;
- dua batch, yaitu kebutuhan mendesak sekarang dan sisanya bulan berikutnya;
- menunda seluruh permintaan.

### VMI

Environment membuat `action_mask` untuk menutup pilihan yang melanggar skor, kapasitas, tenggat, atau pengecualian akibat negosiasi sebelumnya. Semua vendor yang lolos terlebih dahulu memberi penawaran awal dan merespons permintaan harga pembeli. Setelah harga tiap kandidat tersedia, VMI memilih A, B, atau C. Biaya pembanding mencakup harga penawaran, transportasi, dan risiko.

### DA

DA menentukan cara bernegosiasi:

- menerima penawaran kandidat hasil putaran kompetitif;
- memberi penawaran balik lanjutan kepada kandidat terpilih;
- meminta vendor alternatif.

Harga balasan ditentukan oleh utilitas vendor. Penerimaan revisi termin dipengaruhi utilitas dan seed simulasi; seed yang sama membuat hasil dapat diulang.

Sebelum VMI memilih, setiap vendor yang lolos membandingkan tawaran pembeli dengan harga reservasi yang dipengaruhi harga minimum, relasi, tekanan kapasitas, besar pesanan, jumlah pesaing, dan karakter konsesi. Negosiasi dapat berlangsung sampai tiga ronde internal per vendor. DA boleh mencoba menawar lagi setelah VMI memilih. Setiap respons dicatat sebagai langkah `VENDOR A`, `VENDOR B`, atau `VENDOR C`, meskipun vendor bukan bagian dari empat policy MARL pembeli.

Harga minimum bawaan ialah A Rp90.000, B Rp86.500, dan C Rp101.000. Jika tawaran pembeli mencapai harga vendor, hasilnya sepakat. DA mendapat penalti −0,35 saat meminta alternatif yang tidak menurunkan biaya pembelian dan logistik dibanding kandidat sebelumnya.

### SLM

SLM mengevaluasi dampak pembayaran dan memilih:

- pembayaran cepat dengan diskon;
- pembayaran saat jatuh tempo;
- usulan termin terpisah;
- meminta revisi skenario.

Aksi meminta revisi adalah aksi model yang sungguh dilatih. Pada skenario yang terbukti kekurangan dana, aksi ini memperoleh reward positif. Pada skenario yang sebenarnya masih mungkin, permintaan revisi terlalu dini diberi penalti.

Generator latihan membuat sekitar 20% episode dengan kekurangan dana yang dibuktikan dari batas bawah biaya. SLM menerima indikator dan besar kekurangan itu dalam observasi lokalnya. Ini memberi contoh positif dan negatif yang cukup agar model dapat mempelajari kapan harus meminta revisi.

### Evaluator Sistem

Evaluator Sistem bukan agen pembelajar. Ia menghitung biaya dan kas, lalu memeriksa anggaran, kapasitas, tenggat, kebutuhan mendesak, dan **cadangan kas minimum Rp60 juta pada setiap bulan**. Di UI evaluator memiliki kotak tersendiri agar tidak terlihat seolah menjadi agen kelima.

## 3. Mengapa proses dapat berhenti lebih awal

`cash_diagnosis()` menghitung batas bawah biaya. Dana tersedia untuk belanja adalah kas awal + arus masuk − kewajiban lain − cadangan kas wajib. Perhitungan sengaja memakai harga terbaik yang mungkin, bahkan tanpa membatasi kapasitas vendor. Karena nilainya optimistis, jika dana belanja masih lebih kecil dari batas biaya tersebut, tidak ada perubahan termin pembayaran yang dapat membuat saldo akhir mencapai Rp60 juta.

Hasil akhir mempunyai tiga arti:

- **LAYAK**: semua kendala rencana terpenuhi, termasuk cadangan kas minimum tiap bulan.
- **PERLU REVISI**: episode berhenti tanpa bukti matematis bahwa skenario mustahil, sehingga input atau rencana perlu diperiksa.
- **TIDAK FEASIBLE**: batas bawah biaya melampaui dana belanja setelah cadangan wajib disisihkan.

Environment juga menghentikan pengulangan rencana material yang sama dengan alasan `no_progress`. Ini mencegah model berputar sampai batas enam siklus tanpa menghasilkan perubahan.

## 4. IQL dan CTDE benar-benar dilatih

### IQL

`src/procurement_marl/agents/iql.py` menyimpan Q-table terpisah untuk IRE, VMI, DA, dan SLM. Setiap agen hanya membaca observasi lokalnya. Pembaruan memakai rumus Q-learning:

```text
Q(s,a) ← Q(s,a) + α [r + γ max Q(s',a') − Q(s,a)]
```

### CTDE

`src/procurement_marl/agents/ctde_ac.py` memakai actor lokal yang terpisah untuk setiap agen dan satu critic yang membaca state gabungan saat pelatihan. Actor hanya memakai observasi lokal saat aplikasi dijalankan. Replay buffer bersama dipakai untuk melatih critic; actor diperbarui dari episode baru agar pembaruan kebijakannya tetap sesuai data terbaru.

Checkpoint disimpan di `runs/iql/` dan `runs/ctde/`. Mengganti observasi, jumlah aksi, atau reward mengharuskan pelatihan ulang. Versi model, jumlah episode, seed pelatihan, lokasi checkpoint, dan hash SHA-256 masuk ke laporan agar hasil dapat diaudit.

## 5. Baseline ML sesuai laporan

Baseline supervised learning mempunyai tugas yang berbeda dari agen:

1. IQL atau CTDE mengendalikan IRE, VMI, DA, dan SLM untuk membuat rencana.
2. `decision_features()` mengubah rencana akhir menjadi 24 fitur terstruktur, misalnya rasio anggaran, biaya per unit, kas akhir, kualitas vendor, kapasitas, lead time, dan jenis pembayaran.
3. Logistic Regression, SVM, Random Forest, dan XGBoost mengklasifikasikan keputusan sebagai optimal atau tidak optimal.
4. XGBoost menjadi pembanding utama pada dashboard karena accuracy dan ROC-AUC test tertinggi pada artefak yang disertakan.

Baseline tidak memilih vendor, tidak menegosiasikan harga, dan tidak mengubah status LAYAK/PERLU REVISI/TIDAK FEASIBLE. Status tersebut tetap berasal dari aturan environment.

Dataset historis organisasi yang disebut laporan tidak disertakan dalam proyek. `train_baseline.py` karena itu membuat data simulasi secara transparan. Kandidat diberi label optimal bila layak dan biayanya tidak lebih dari 103% biaya layak terendah dari kandidat yang diuji pada skenario yang sama. Train/test dipisahkan berdasarkan skenario untuk mencegah kebocoran data. CSV, model, versi pustaka, aturan label, metrik, dan confusion matrix disimpan di `runs/baseline/`.

Jejak audit CSV memuat kas bulan 1–4. Saat vendor menanggapi revisi termin, log mencatat utilitas, probabilitas menerima, serta angka acak dari seed. Respons diterima jika angka acak lebih kecil daripada probabilitas. Untuk pengujian oracle, angka acak diganti keputusan paksa dan ditandai dalam event.

## 6. Isi database

`procurement/rl_storage.py` membuat tiga tabel:

- `marl_runs`: satu baris untuk setiap skenario, berisi input, metode, seed, status, biaya, jumlah siklus, dan laporan JSON;
- `marl_events`: semua tindakan dan pemeriksaan environment, berurutan berdasarkan langkah.
- `vendor_settings`: satu konfigurasi aktif Vendor A/B/C yang digunakan oleh skenario berikutnya.

Penyimpanan dilakukan dalam satu transaksi. Jika penyimpanan event gagal, baris skenario juga dibatalkan sehingga laporan tidak terpisah dari jejaknya.

## 7. Pemeriksaan vendor bertahap

Sebelum model VMI memilih vendor, environment menghitung aturan yang diperlukan oleh `action_mask`. Agar proses ini transparan, pemeriksaan tersebut dicatat sebagai event, bukan disamarkan sebagai aksi belajar:

1. `vendor_check_start` mengubah satu vendor menjadi **Sedang diperiksa**;
2. `vendor_screening` mencatat skor, kapasitas, tenggat, dan pengecualian;
3. setelah A/B/C selesai, kebijakan IQL atau CTDE memilih salah satu vendor yang lolos;
4. DA memperbarui harga atau mengeluarkan vendor;
5. SLM memperbarui cara pembayaran.

Tabel pada tab Proses dibangun ulang dari event sampai posisi slider. Karena itu langkah pertama hanya menunjukkan **Belum diperiksa** dan tidak membocorkan keputusan akhir.

## 8. Mengedit vendor

Tab **Konfigurasi vendor** mengizinkan perubahan harga daftar, penawaran awal, harga minimum, transportasi, risiko, kualitas, lead time, kapasitas, diskon, reputasi, dan relasi. Validasi memastikan harga minimum ≤ penawaran awal ≤ harga daftar serta seluruh rentang angka masuk akal.

Konfigurasi baru hanya digunakan ketika tombol menjalankan skenario ditekan. Skenario lama membaca snapshot dari `marl_runs`, sehingga hasil historis tidak ikut berubah. Jumlah vendor tetap A/B/C dan struktur observasi serta action space tidak berubah; checkpoint tidak perlu dilatih ulang untuk penambahan fitur audit dan editor ini.

## 9. Hubungan fail utama

| Fail | Kegunaan |
|---|---|
| `app.py` | Form input, tampilan proses, pelaporan, dan unduhan audit |
| `procurement/rl_service.py` | Membuat skenario, memuat model, menjalankan episode, dan membuat laporan singkat |
| `procurement/rl_storage.py` | Menulis dan membaca SQLite |
| `procurement/baseline_ml.py` | Membentuk fitur keputusan dan menjalankan baseline klasifikasi |
| `src/procurement_marl/env.py` | Aturan giliran, aksi, reward, kendala, serta penghentian episode |
| `src/procurement_marl/vendor_agents.py` | Agen vendor berbasis utilitas, harga reservasi, dan counter offer |
| `src/procurement_marl/scenario.py` | Fixture BAB 6, diagnosis kas, dan pembangkit skenario latihan |
| `src/procurement_marl/costs.py` | Rumus biaya, diskon, jadwal pembayaran, dan saldo kas |
| `scripts/train.py` | Melatih IQL atau CTDE dan menyimpan checkpoint |
| `scripts/train_baseline.py` | Melatih LR, SVM, Random Forest, dan XGBoost serta menyimpan metrik |
| `src/procurement_marl/evaluate.py` | Menjalankan serta mengevaluasi kebijakan dengan aturan yang sama |

## 10. Angka BAB 6

Angka contoh laporan dipertahankan sebagai pembanding rule-based yang terpisah dari keputusan model:

- pengadaan awal melalui Vendor B: **Rp99.710.000**, kas **−Rp19.710.000**;
- skenario bertahap 700 B + 300 A: **Rp100.397.000**, kas bulan kedua **−Rp20.397.000**.

Keduanya tetap ditampilkan sebagai belum layak. Model IQL atau CTDE boleh memilih tindakan yang berbeda, tetapi evaluator menggunakan rumus kendala yang sama dan tidak mengubah hasil gagal menjadi sukses hanya karena reward tinggi.
