# Benchmark tambahan dan clustering BPI

Semua kandidat memakai partisi temporal dan kelompok dokumen yang sama per agen. Model utama memakai label pendekatan dari kejadian BPI; clustering tidak memakai label saat fit. Tidak ada pilihan akhir yang dikunci.

## IRE — Tinjau kebutuhan: prediksi revisi jumlah setelah PO dibuat

Rekomendasi berdasarkan macro-F1 validasi: **Cluster+Logistic**. Mayoritas pada uji: 97.19%.

| Kandidat | Accuracy train | Accuracy validasi | Accuracy uji | Macro-F1 validasi | Macro-F1 uji |
|---|---:|---:|---:|---:|---:|
| Decision Tree | 69.41% | 87.06% | 84.35% | 0.486 | 0.528 |
| CatBoost | 94.54% | 98.33% | 97.28% | 0.496 | 0.570 |
| SVM (linear) | 70.44% | 95.34% | 95.38% | 0.511 | 0.588 |
| Logistic Regression | 69.96% | 95.28% | 95.38% | 0.499 | 0.586 |
| Random Forest | 73.08% | 94.56% | 92.31% | 0.506 | 0.571 |
| Extra Trees | 63.72% | 88.56% | 84.57% | 0.479 | 0.512 |
| SGD log-loss | 65.63% | 97.33% | 96.97% | 0.493 | 0.587 |
| AdaBoost | 94.62% | 98.33% | 97.32% | 0.496 | 0.571 |
| XGBoost | 94.69% | 98.33% | 97.35% | 0.496 | 0.572 |
| Cluster+Logistic | 70.31% | 97.28% | 97.19% | 0.513 | 0.574 |

| Clustering | Silhouette validasi | Silhouette uji | ARI terhadap label uji | Ukuran cluster uji |
|---|---:|---:|---:|---|
| MiniBatch K-means | 0.419 | 0.393 | 0.011 | {'3': 4017, '2': 2293, '4': 528, '1': 449, '0': 31} |
| Gaussian mixture | 0.232 | 0.206 | 0.053 | {'4': 6365, '1': 902, '0': 51} |
| BIRCH | 0.408 | 0.374 | 0.022 | {'0': 6290, '4': 825, '3': 111, '2': 88, '1': 4} |

Fitur jarak cluster: accuracy 95.38% → 97.19%, macro-F1 0.586 → 0.574.

## VMI — Nilai risiko transaksi vendor: pelunasan vs penghapusan PO

Rekomendasi berdasarkan macro-F1 validasi: **XGBoost**. Mayoritas pada uji: 88.82%.

| Kandidat | Accuracy train | Accuracy validasi | Accuracy uji | Macro-F1 validasi | Macro-F1 uji |
|---|---:|---:|---:|---:|---:|
| Decision Tree | 89.48% | 77.84% | 59.81% | 0.733 | 0.509 |
| CatBoost | 95.55% | 83.18% | 74.24% | 0.780 | 0.622 |
| SVM (linear) | 78.51% | 69.65% | 44.12% | 0.651 | 0.400 |
| Logistic Regression | 78.41% | 65.35% | 40.39% | 0.618 | 0.373 |
| Random Forest | 76.34% | 73.32% | 62.93% | 0.678 | 0.535 |
| Extra Trees | 76.64% | 80.68% | 69.85% | 0.740 | 0.578 |
| SGD log-loss | 75.80% | 57.86% | 19.31% | 0.564 | 0.193 |
| AdaBoost | 95.82% | 82.52% | 89.10% | 0.611 | 0.581 |
| XGBoost | 96.33% | 86.20% | 76.23% | 0.797 | 0.623 |
| Cluster+Logistic | 79.14% | 43.01% | 24.92% | 0.429 | 0.249 |

| Clustering | Silhouette validasi | Silhouette uji | ARI terhadap label uji | Ukuran cluster uji |
|---|---:|---:|---:|---|
| MiniBatch K-means | 0.395 | 0.333 | 0.027 | {'0': 3708, '2': 3586, '4': 520, '1': 379, '3': 46} |
| Gaussian mixture | 0.389 | 0.089 | -0.036 | {'0': 5299, '1': 1312, '3': 897, '4': 528, '2': 203} |
| BIRCH | 0.359 | 0.388 | -0.039 | {'0': 6867, '3': 902, '4': 300, '1': 166, '2': 4} |

Fitur jarak cluster: accuracy 40.39% → 24.92%, macro-F1 0.373 → 0.249.

## DA — Tinjau penawaran: prediksi kejadian revisi harga

Rekomendasi berdasarkan macro-F1 validasi: **Extra Trees**. Mayoritas pada uji: 96.79%.

| Kandidat | Accuracy train | Accuracy validasi | Accuracy uji | Macro-F1 validasi | Macro-F1 uji |
|---|---:|---:|---:|---:|---:|
| Decision Tree | 75.21% | 89.56% | 86.76% | 0.493 | 0.533 |
| CatBoost | 94.20% | 97.50% | 94.75% | 0.569 | 0.548 |
| SVM (linear) | 84.23% | 91.73% | 87.15% | 0.596 | 0.587 |
| Logistic Regression | 83.68% | 93.34% | 89.59% | 0.621 | 0.586 |
| Random Forest | 76.73% | 87.34% | 85.00% | 0.499 | 0.550 |
| Extra Trees | 75.82% | 96.34% | 88.74% | 0.647 | 0.574 |
| SGD log-loss | 81.54% | 97.83% | 94.37% | 0.495 | 0.547 |
| AdaBoost | 95.76% | 98.00% | 96.79% | 0.495 | 0.492 |
| XGBoost | 96.13% | 98.00% | 96.79% | 0.495 | 0.492 |
| Cluster+Logistic | 83.38% | 96.00% | 94.07% | 0.581 | 0.554 |

| Clustering | Silhouette validasi | Silhouette uji | ARI terhadap label uji | Ukuran cluster uji |
|---|---:|---:|---:|---|
| MiniBatch K-means | 0.478 | 0.424 | -0.013 | {'1': 4014, '4': 1486, '0': 1156, '2': 525, '3': 137} |
| Gaussian mixture | 0.065 | 0.190 | -0.007 | {'1': 7289, '0': 29} |
| BIRCH | 0.395 | 0.371 | -0.023 | {'0': 6262, '4': 825, '2': 117, '3': 110, '1': 4} |

Fitur jarak cluster: accuracy 89.59% → 94.07%, macro-F1 0.586 → 0.554.

## SLM — Perkirakan jeda pembayaran: ≤7, >7–30, atau >30 hari

Rekomendasi berdasarkan macro-F1 validasi: **CatBoost**. Mayoritas pada uji: 39.16%.

| Kandidat | Accuracy train | Accuracy validasi | Accuracy uji | Macro-F1 validasi | Macro-F1 uji |
|---|---:|---:|---:|---:|---:|
| Decision Tree | 65.08% | 70.27% | 53.50% | 0.319 | 0.398 |
| CatBoost | 79.95% | 74.02% | 55.63% | 0.426 | 0.440 |
| SVM (linear) | 78.60% | 79.85% | 58.93% | 0.419 | 0.436 |
| Logistic Regression | 71.22% | 58.89% | 45.73% | 0.287 | 0.340 |
| Random Forest | 68.92% | 63.80% | 50.64% | 0.326 | 0.393 |
| Extra Trees | 70.49% | 64.55% | 53.27% | 0.311 | 0.419 |
| SGD log-loss | 75.40% | 80.37% | 58.39% | 0.353 | 0.401 |
| AdaBoost | 71.71% | 76.79% | 59.32% | 0.298 | 0.359 |
| XGBoost | 77.11% | 77.77% | 60.05% | 0.360 | 0.379 |
| Cluster+Logistic | 73.04% | 60.85% | 48.94% | 0.357 | 0.365 |

| Clustering | Silhouette validasi | Silhouette uji | ARI terhadap label uji | Ukuran cluster uji |
|---|---:|---:|---:|---|
| MiniBatch K-means | 0.491 | 0.479 | 0.032 | {'3': 3863, '0': 1343, '4': 754, '2': 498, '1': 465} |
| Gaussian mixture | 0.138 | 0.214 | -0.016 | {'2': 6563, '4': 347, '0': 13} |
| BIRCH | 0.455 | 0.420 | 0.033 | {'1': 5984, '4': 752, '3': 107, '0': 75, '2': 5} |

Fitur jarak cluster: accuracy 45.73% → 48.94%, macro-F1 0.340 → 0.365.

## Catatan

K-means, Gaussian mixture, dan BIRCH menargetkan lima cluster dari embedding SVD hasil training. Cluster kecil atau hilang pada periode uji menunjukkan distribusi berubah. Silhouette bukan accuracy. ARI dekat nol menunjukkan cluster tidak dapat menggantikan label keputusan.

Eksperimen Cluster+Logistic pada VMI, DA dan SLM mencapai batas iterasi solver; hasilnya bersifat eksplorasi. Periode uji telah dipakai pada eksperimen sebelumnya, bukan validasi eksternal independen. Tidak ada klaim bebas overfitting.

Animasi portal memakai HTML/CSS/JS, tanpa library animasi. Adegan telepon dan email bersifat simulasi dan menghormati pengaturan reduced-motion.
