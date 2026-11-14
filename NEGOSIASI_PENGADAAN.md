# Negosiasi pengadaan · PT. Biz Indonesia Market

Restart `procurement_web.py` dan buka http://127.0.0.1:8080. Pilih salah satu
dari sepuluh kategori, isi jumlah, plafon anggaran, proyeksi bulan, tenggat,
dan termin. **Hitung ulang minimum** memakai syarat tersebut. Bobot ditetapkan
di `config/buyer_policy.json` dan ditampilkan terpisah pada menu Aturan pembeli.
**Jalankan negosiasi** menyimpan keputusan, jejak tawar balik, dan cadangan
pengeluaran. Alur dapat diputar atau ditelusuri dengan Maju/Mundur.

## Sumber dan minimum acuan

Kandidat berasal dari katalog training BPI yang disetujui: lima vendor berbeda
per konteks dengan tipe item dan dokumen yang sama. Nama PT merupakan alias.
Tidak ada impor Excel. BPI tidak berisi biaya barang per unit, gaji, ongkir,
kapasitas, margin vendor, atau syarat kontrak yang dibutuhkan simulasi ini.
Angka PO anonim hanya menjadi skala awal. Semua profil biaya dan kebijakan
vendor adalah **asumsi simulasi**, bukan tarif aktual atau rupiah.

| Pengadaan | Minimum awal (satuan BPI) |
|---|---:|
| Products for Resale | 124,29 |
| Labels | 162,04 |
| Metal Containers & Lids < 30L | 393,78 |
| Plastic Containers & Lids < 30L | 969,72 |
| Trading products (old structure) | 71,74 |
| Extenders | 1.915,95 |
| Road Packed | 19,10 |
| MRO (components) | 235,22 |
| Surfactants | 41,18 |
| Laboratory Supplies & Services | 171,05 |

Acuan: 10 unit, proyeksi 0 bulan, tenggat 21 hari, bayar 30 hari. Minimum
bukan anggaran yang dipaksa: pembeli boleh menawar di bawahnya dan melihat
hasil gagal. Jika tidak ada vendor memenuhi syarat non-anggaran, plafon
yang lebih tinggi saja tidak menyelesaikan masalah.

## Biaya, tawaran, dan penilaian

- Biaya barang proyeksi/unit = biaya kini × (1 + perubahan bulanan)^bulan.
  Total biaya = jumlah × (biaya barang proyeksi + alokasi tenaga kerja/unit)
  + pengiriman + overhead. Tenaga kerja adalah alokasi biaya, bukan data gaji asli.
- Minimum margin adalah terhadap pendapatan. Dengan biaya 900 dan margin
  minimum 10%, batas harga = 900 ÷ (1 − 10%) = 1.000. Diskon maksimum dapat
  memperketat batas ini. Lantai dibulatkan ke atas hingga dua desimal.
- Vendor gugur jika kapasitas, modal untuk menalangi biaya, tenggat atau batas
  termin tidak terpenuhi. Aturan berbeda per vendor/kategori, tersimpan pada
  `negotiation_vendor_rules` di SQLite dan ditampilkan pada menu Aturan vendor.
- Pembeli memberi tawar balik dengan plafon anggaran. Vendor menerima jika
  batasnya terpenuhi; jika tidak, memberi konsesi hingga maksimal tiga putaran.
- Bobot kebijakan perusahaan: harga 45%, kirim 20%, kualitas 20%, risiko 15%.
  Formulir transaksi tidak menimpa bobot ini.
  Harga dinormalisasi terhadap penawaran final termurah yang sepakat, pengiriman
  terhadap lead time tercepat, kualitas memakai skor asumsi, risiko memakai
  satu dikurangi skor risiko. Kontribusi tiap bobot terlihat pada tabel.
- Rencana pengeluaran menampilkan cadangan harga final, sisa plafon dan usulan
  hari bayar setelah invoice. Nilai 0 dicadangkan bila gagal/tidak ada vendor.

## Empat model tanpa duplikasi

| Agen | Model tetap | Macro-F1 validasi | Accuracy uji | Alasan dan tanggung jawab |
|---|---|---:|---:|---|
| IRE | SVM linear | 0,511 | 95,38% | Macro-F1 validasi tertinggi dari kandidat tanpa clustering untuk sinyal revisi jumlah. Accuracy di bawah baseline mayoritas; hasil tetap berupa sinyal tinjauan. |
| VMI | XGBoost | 0,797 | 76,23% | Skor validasi terbaik untuk risiko pelunasan/penghapusan. Prediksi menambah penalti risiko pada bobot, bukan menentukan biaya atau menggugurkan vendor sendiri. |
| DA | Extra Trees | 0,647 | 88,74% | Skor validasi terbaik untuk riwayat revisi harga. Mengubah laju konsesi; tawar balik dan keputusan tetap dihitung dari biaya, margin, dan plafon. |
| SLM | CatBoost | 0,426 | 55,63% | Skor validasi terbaik untuk kelompok jeda pembayaran. Menjadi saran; termin dipilih pembeli dan diperiksa terhadap batas vendor. |

Pilihan memakai hasil benchmark sebelumnya, bukan training ulang. Statistik
terperinci tetap bisa dilihat di menu Model agen; ARI clustering rendah dan
tidak mendukung clustering murni sebagai pengganti keputusan transaksi.

## Pengiriman

Ilustrasi SVG/CSS lokal: permintaan, negosiasi, paket di gudang, truk bergerak,
dan penerimaan. Menghormati reduced-motion dan tanpa library eksternal.
Alur packing/pengiriman/penerimaan hanya muncul bila ada kesepakatan simulasi.
Tidak ada pesan, pemesanan, pemindahan barang atau pembayaran nyata.
