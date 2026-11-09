# Contoh simulasi PT. Biz Indonesia Market

Pada panel kiri, pilih **Simulasi MARL** atau **Simulasi CatBoost**. Keduanya
tersedia dalam aplikasi yang sama. Masing-masing mempunyai menu contoh:
pilih contoh → klik **Terapkan contoh** → klik **Buat & jalankan skenario**.
Contoh dapat diedit sebelum dijalankan. Gunakan Maju/Mundur untuk membaca alurnya.

## MARL: IQL dan CTDE

Hasil berikut benar-benar dijalankan dengan checkpoint saat ini dan konfigurasi
vendor bawaan laporan. Uang menggunakan rupiah. Jika konfigurasi vendor diubah,
hasil dapat berubah. Contoh tidak menghapus atau mengganti konfigurasi aktif.

| Contoh | Unit / mendesak | Anggaran | Seed | IQL | CTDE |
|---|---|---:|---:|---|---|
| Pembelian ringan | 500 / 50 | Rp100 juta | 0 | LAYAK, Rp49.007.850 | LAYAK, Rp48.892.000 |
| Semua unit mendesak | 700 / 700 | Rp100 juta | 0 | LAYAK, Rp68.892.600 | LAYAK, Rp68.637.800 |
| Anggaran ketat | 600 / 100 | Rp55 juta | 0 | PERLU REVISI | PERLU REVISI |
| Kekurangan dana acuan laporan | 1.000 / 700 | Rp100 juta | 0 | TIDAK FEASIBLE | TIDAK FEASIBLE |
| Bandingkan IQL dengan CTDE | 600 / 100 | Rp100 juta | 0 | LAYAK, Rp58.828.600 | LAYAK, Rp58.685.000 |
| Respons vendor dengan seed berbeda | 600 / 100 | Rp100 juta | 7 | LAYAK | LAYAK |

Seed berbeda tidak wajib menghasilkan keputusan berbeda. Dalam contoh terakhir,
hasil akhir sama dengan seed 0; ini hasil aktual, bukan hasil yang dipaksakan.

Vendor pada tampilan MARL:

- PT. Aruna Niaga Nusantara (slot model A).
- PT. Bina Sumber Sejahtera (slot model B).
- PT. Cakra Mitra Utama (slot model C).

Slot model dan checkpoint tidak diubah. Konfigurasi vendor menampilkan nama PT,
tetapi mengembalikan ID asli ke backend sebelum validasi/perhitungan.

## CatBoost: lima contoh dari BPI

Nilai menggunakan satuan PO BPI anonim, berbeda dengan rupiah pada simulator
MARL. Tanggal contoh adalah 1 September 2018. Kandidat minimal lima vendor pada
konteks yang sama. Batas nilai dihitung dari penawaran kategori tersebut.

| Contoh | Tujuan | Hasil dengan konfigurasi bawaan |
|---|---|---|
| Kantor — anggaran longgar | Mengikuti lima vendor hingga evaluasi | LANJUTKAN KE REVIEW PEMBELIAN |
| Kantor — semua melewati anggaran | Menguji penyaringan anggaran | Tidak ada penawaran dalam anggaran |
| Perangkat IT | Membandingkan vendor pada kategori IT | TINJAU ULANG PENAWARAN |
| Kemasan | Menguji permintaan kategori lain | TINJAU ULANG PENAWARAN |
| Fasilitas — anggaran menengah | Menyaring sebagian penawaran | LANJUTKAN KE REVIEW PEMBELIAN |

Hasil merupakan saran model dari pendekatan label transaksi BPI. Tidak otomatis
berarti pembelian sudah disetujui atau pembayaran sudah dilakukan. Persetujuan
simulasi dapat dicatat pada tab Pelaporan. Riwayat transaksi aktual BPI
ditampilkan terpisah di tab yang sama.

## Nama vendor dan penyimpanan

Seluruh 1.975 ID vendor BPI diberi **alias PT fiktif yang unik**. Alias konsisten
pada tabel, kartu agen, konfigurasi vendor, dan riwayat. Nama ini bukan nama
perusahaan nyata yang berhasil diungkap dari BPI; sumber memang dianonimkan.
ID asli tetap tersedia dalam data/audit terstruktur dan tetap dipakai model.

Hasil 17 percobaan disimpan pada `runs/simulation_examples.json`. Untuk mengulang
tanpa menambah riwayat transaksi pengguna:

```powershell
python scripts/check_simulation_examples.py
```
