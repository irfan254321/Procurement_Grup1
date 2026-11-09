"""Repeatable inputs; expectations are teaching goals, not fixed model answers."""
MARL_EXAMPLES={
 '1. Pembelian ringan':{'quantity':500,'urgent':50,'budget':100_000_000,'seed':0,'goal':'Telusuri pembagian pesanan dan hasil kelayakan.'},
 '2. Semua unit mendesak':{'quantity':700,'urgent':700,'budget':100_000_000,'seed':0,'goal':'Bandingkan satu batch dengan pesanan yang dibagi.'},
 '3. Anggaran ketat':{'quantity':600,'urgent':100,'budget':55_000_000,'seed':0,'goal':'Lihat respons agen ketika anggaran lebih ketat.'},
 '4. Kekurangan dana acuan laporan':{'quantity':1000,'urgent':700,'budget':100_000_000,'seed':0,'goal':'Lihat diagnosis kekurangan dana dan permintaan revisi.'},
 '5. Bandingkan IQL dengan CTDE':{'quantity':600,'urgent':100,'budget':100_000_000,'seed':0,'goal':'Jalankan input sama dengan IQL dan CTDE.'},
 '6. Respons vendor dengan seed berbeda':{'quantity':600,'urgent':100,'budget':100_000_000,'seed':7,'goal':'Bandingkan dengan seed 0; pilihan model dan respons vendor dapat berbeda.'},
}
CATBOOST_EXAMPLES={
 '1. Kantor — anggaran longgar':{'sub':'Office Supplies','budget_factor':1.25,'goal':'Periksa lima penawaran perlengkapan kantor dan peringkat kandidat.'},
 '2. Kantor — semua melewati anggaran':{'sub':'Office Supplies','budget_factor':0.,'goal':'Lihat hasil tanpa kandidat yang memenuhi anggaran.'},
 '3. Perangkat IT':{'sub':'ICT Hardware','budget_factor':1.25,'goal':'Telusuri penilaian lima vendor perangkat IT.'},
 '4. Kemasan':{'sub':'Packaging - Other','budget_factor':1.25,'goal':'Coba permintaan berbeda; vendor dan nilainya mengikuti konteks kategori.'},
 '5. Fasilitas — anggaran menengah':{'sub':'Facility Management','budget_factor':.5,'goal':'Lihat penyaringan vendor oleh batas anggaran.'},
}
