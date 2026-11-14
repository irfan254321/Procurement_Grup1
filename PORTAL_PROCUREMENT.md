# Portal Procurement · PT. Biz Indonesia Market

Jalankan dari PowerShell di folder proyek:

```powershell
.\.venv\Scripts\python.exe procurement_web.py
```

Buka http://127.0.0.1:8080. Portal lokal HTML/CSS/JS dengan server Python ini
menyediakan permintaan pengadaan, evaluasi lima vendor, pilihan satu model per
agen, perbandingan metrik, riwayat SQLite, dan bukti pelunasan historis BPI.
Tidak ada mode MARL atau dependensi Streamlit untuk menjalankan portal.
Model yang terpilih di formulir hanya berlaku pada simulasi itu; keputusan
model final per agen menunggu pilihan pengguna.

## Empat agen dan batas label BPI

| Agen | Tugas yang dipelajari | Arti hasil |
|---|---|---|
| IRE | Prediksi revisi jumlah setelah pembuatan PO | Saran meninjau kebutuhan; tidak menentukan jumlah baru atau urgensi |
| VMI | Prediksi pelunasan vs penghapusan item PO | Sinyal risiko kandidat vendor; tidak membuktikan vendor terbaik atau persetujuan tawaran |
| DA | Prediksi kejadian revisi harga | Saran tinjauan harga; tidak menghitung nominal tawar balik |
| SLM | Prediksi jeda dari invoice ke pelunasan | Kelompok ≤7, >7–30, >30 hari; bukan termin kontrak |

Evaluator anggaran adalah validasi angka, tidak memerlukan model kelima.
Pembelian tetap membutuhkan keputusan manusia. Semua nama PT vendor adalah
alias simulasi; model menggunakan ID BPI. Model IRE tidak memakai identitas
vendor, sehingga revisi kebutuhan tidak didasarkan pada vendor yang dipilih.

## Benchmark yang dijalankan

Decision Tree teratur, CatBoost dengan early stopping, dan SVM linear
dibandingkan pada partisi waktu/dokumen yang sama per tugas. Preprocessing
Decision Tree/SVM dipasang hanya pada train. Rekomendasi ditetapkan dari
macro-F1 validasi. Periode uji ini sudah dipakai pada eksperimen sebelumnya;
hasil tidak merupakan validasi eksternal baru. Snapshot kategori PO dipakai
sebagai konteks yang diasumsikan diketahui. IRE dan DA memiliki kelas revisi
langka; sebagian model dengan accuracy tinggi mengabaikan kelas minoritas.

| Agen | Decision Tree accuracy / F1 | CatBoost accuracy / F1 | SVM linear accuracy / F1 | Rekomendasi dari validasi |
|---|---|---|---|---|
| IRE | 84,35% / 0,528 | 97,28% / 0,570 | 95,38% / 0,588 | SVM linear |
| VMI | 59,81% / 0,509 | 74,24% / 0,622 | 44,12% / 0,400 | CatBoost |
| DA | 86,76% / 0,533 | 94,75% / 0,548 | 87,15% / 0,587 | SVM linear |
| SLM | 53,50% / 0,398 | 55,63% / 0,440 | 58,93% / 0,436 | CatBoost |

VMI CatBoost paling kuat dari tiga kandidat uji, tetapi accuracy masih di bawah
tebakan mayoritas 88,82%. DA juga belum melampaui baseline mayoritas 96,79%.
SLM SVM lebih tinggi pada accuracy, sedangkan CatBoost sedikit lebih seimbang
antar kelas. Model CatBoost benchmark berbeda konfigurasi dari model lama v2;
angka ini bukan klaim bahwa benchmark menggantikan atau mengungguli v2.

Artefak: `runs/agent_benchmark/results.json` dan 12 file model. Untuk mengulang,
jalankan `python benchmark_agents.py` setelah database BPI dan tabel training
penawaran tersedia. Portal memakai artefak lokal yang dihasilkan sendiri.
