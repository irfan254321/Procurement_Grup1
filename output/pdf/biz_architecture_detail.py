"""Detailed vector architecture pages for the BIZ District report."""
import math
from reportlab.lib import colors
from reportlab.lib.pagesizes import A2, A3, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph

INK = colors.HexColor('#183444')
BLUE = colors.HexColor('#086FAD')
GREEN = colors.HexColor('#4F8A5C')
RED = colors.HexColor('#B33F48')
MUTED = colors.HexColor('#5E707B')
LINE = colors.HexColor('#C9D6DD')
PALE = colors.HexColor('#F0F5F7')
LIGHTBLUE = colors.HexColor('#EAF3F9')
LIGHTGREEN = colors.HexColor('#EDF5EF')
LIGHTRED = colors.HexColor('#FCF0EF')
WHITE = colors.white


class Diagram:
    def __init__(self, report):
        self.r = report
        self.c = report.c

    def text(self, text, x, top, width, size=12, leading=None, color=INK, bold=False, align=0):
        style = ParagraphStyle('diagram_detail', fontName='Calibri-Bold' if bold else 'Calibri',
                               fontSize=size, leading=leading or size * 1.28, textColor=color, alignment=align)
        para = Paragraph(text, style)
        _, height = para.wrap(width, 2000)
        para.drawOn(self.c, x, top - height)
        return height

    def node(self, x, y, w, h, title, body, color=BLUE, fill=WHITE, size=11.5, header=28):
        c = self.c
        c.setFillColor(fill)
        c.setStrokeColor(LINE)
        c.setLineWidth(.9)
        c.roundRect(x, y, w, h, 7, fill=1, stroke=1)
        c.setFillColor(color)
        c.roundRect(x, y + h - header, w, header, 5, fill=1, stroke=0)
        title_height = self.text(title, x + 12, y + h - 7, w - 24, size + .5, size + 3, WHITE, True)
        if title_height > header - 7:
            raise ValueError(f'Header too tall: {title}')
        used = self.text(body, x + 12, y + h - header - 11, w - 24, size, size * 1.31)
        if used > h - header - 19:
            raise ValueError(f'Node overflow {title}: {used} > {h-header-19}')

    def arrow(self, points, color=GREEN, dashed=False, width=1.6, head=True):
        c = self.c
        c.saveState()
        c.setStrokeColor(color)
        c.setLineWidth(width)
        c.setDash(6, 4) if dashed else c.setDash()
        p = c.beginPath()
        p.moveTo(*points[0])
        for point in points[1:]:
            p.lineTo(*point)
        c.drawPath(p)
        c.setDash()
        if head:
            a, b = points[-2], points[-1]
            theta = math.atan2(b[1] - a[1], b[0] - a[0])
            for angle in [-.46, .46]:
                c.line(b[0], b[1], b[0] - 7 * math.cos(theta + angle), b[1] - 7 * math.sin(theta + angle))
        c.restoreState()

    def label(self, text, x, y, w, color=MUTED, size=10):
        self.c.setFillColor(WHITE)
        self.c.rect(x, y - 3, w, 17, fill=1, stroke=0)
        self.text(text, x + 3, y + 11, w - 6, size, size * 1.2, color, align=1)

    def strip(self, x, y, w, title, color=BLUE, height=27):
        self.c.setFillColor(color)
        self.c.roundRect(x, y, w, height, 4, fill=1, stroke=0)
        self.text(title, x + 9, y + height - 6, w - 18, 12, 15, WHITE, True)

    def badge(self, value, x, y, color=BLUE):
        self.c.setFillColor(color)
        self.c.circle(x, y, 11, fill=1, stroke=0)
        self.c.setFillColor(WHITE)
        self.c.setFont('Calibri-Bold', 12)
        self.c.drawCentredString(x, y - 4, value)


def draw_detailed_pages(report):
    draw_complete(report)
    draw_workflow(report)
    draw_training(report)


def draw_complete(report):
    report.page('Arsitektur detail: data, model, aturan, dan aksi',
                'Setiap kartu menunjukkan input, keluaran classifier, dan pengaruhnya pada keputusan aktual. Baca dari atas ke bawah.', landscape(A2))
    d = Diagram(report)
    c = report.c
    right = report.w - 48
    d.node(48, 960, 300, 108, '1  BROWSER / DUNIA 3D',
           'Putar, jeda, langkah, reset.<br/>Menampilkan 6 lantai, 5 vendor, pelanggan, kiriman, grafik dan riwayat.', size=12)
    d.node(376, 960, 396, 108, '2  HTTP API + TRANSAKSI',
           'GET world/models; POST step/reset.<br/>BEGIN IMMEDIATE: baca world, jalankan satu fase, simpan JSON, kirim respons.', size=12)
    d.node(800, 960, 480, 108, '3  ORKESTRATOR: server.step()',
           'Pilih fase aktif berdasarkan phase dan case. Bentuk fitur peran; panggil main; terapkan aturan; catat event. Katalog dan model dimuat saat server mulai.', size=12)
    d.node(1308, 960, right - 1308, 108, '4  MEMORI: SQLite / world',
           'tick, phase, products, cash, fund, reserved, queue, case, restock_requests, restock_holds, history, tax.', size=11.8)
    d.arrow([(348, 1014), (376, 1014)])
    d.arrow([(772, 1014), (800, 1014)])
    d.arrow([(1280, 1014), (1308, 1014)])
    d.badge('A', 1264, 1080)
    d.text('A = muat model utama dan katalog sebelum melayani giliran', 880, 1090, 365, 10.5, 13, MUTED, align=2)

    # Shared routing bus. A step activates only the relevant role, not seven parallel decisions.
    d.arrow([(1040, 960), (1040, 930)], head=False)
    centers = [48 + i * 229.5 + 105 for i in range(7)]
    d.arrow([(centers[0], 930), (centers[-1], 930)], head=False)
    d.text('ROUTING FITUR: satu fase aktif per langkah; tujuh peran dijalankan bergiliran', 48, 951, 730, 11, 14, MUTED)
    cards = [
        ('PEMBELI', 'CatBoost', 'Pelanggan / lobi L1',
         '<b>Input</b><br/>Harga/unit termasuk PPN; anggaran/unit; jumlah.<br/><br/><b>Output</b><br/>Beli / Lewat.<br/><br/><b>Dipakai untuk</b><br/>Minat beli: prediksi Beli DAN anggaran mencukupi. Belum menjamin stok tersedia.'),
        ('PENJUAL', 'Random Forest', 'Toko L2',
         '<b>Input</b><br/>Stok; permintaan unit; harga jual dasar.<br/><br/><b>Output</b><br/>Layani / Tunda.<br/><br/><b>Dipakai untuk</b><br/>Penjualan memerlukan model Layani, minat beli, anggaran cukup, dan stok nyata mencukupi.'),
        ('STOCK', 'Logistic Regression', 'Gudang L3',
         '<b>Input</b><br/>Stok; permintaan tercatat; titik pesan (3).<br/><br/><b>Output</b><br/>Restok perlu / Stok cukup.<br/><br/><b>Dipakai untuk</b><br/>Kebutuhan mendatang. Stok &lt;=3 atau kekurangan stok juga dapat memicu restok langsung.'),
        ('PENGADAAN', 'SVM', 'Pengadaan L5',
         '<b>Input</b><br/>Penawaran; acuan harga; kapasitas; kebutuhan.<br/><br/><b>Output</b><br/>Prioritas / Bandingkan.<br/><br/><b>Dipakai untuk</b><br/>Urutan vendor, lalu harga dan nama. Semua kandidat tetap diperiksa. Tidak memilih pemenang akhir.'),
        ('VENDOR', 'Gradient Boosting', 'Lima gedung vendor',
         '<b>Input</b><br/>Tawaran pembeli; floor; jumlah; kapasitas.<br/><br/><b>Output</b><br/>Terima / Tawar balik.<br/><br/><b>Dipakai untuk</b><br/>Pada respons vendor: model Terima, harga &gt;=floor, jumlah &lt;=kapasitas. Model sama untuk semua vendor.'),
        ('NEGOSIASI', 'KNN (k=19)', 'Negosiasi L6',
         '<b>Input</b><br/>Harga; batas pembeli; floor vendor.<br/><br/><b>Output</b><br/>Sepakat / Lanjut tawar.<br/><br/><b>Dipakai untuk</b><br/>Gate setelah vendor menerima. Nilai tawar balik dihitung rumus; prediksi saat counter hanya dicatat.'),
        ('KEUANGAN', 'XGBoost', 'Keuangan L4',
         '<b>Input</b><br/>Biaya dasar; dana tersedia; potensi pendapatan.<br/><br/><b>Output</b><br/>Layak / Tahan.<br/><br/><b>Dipakai untuk</b><br/>Pembanding dan log. Persetujuan tetap memakai perhitungan kas, pagu, dan markup minimal 15%.'),
    ]
    for i, (role, model, area, body) in enumerate(cards):
        x = 48 + i * 229.5
        d.arrow([(x + 105, 930), (x + 105, 895)])
        d.node(x, 588, 210, 307, role,
               f'<font color="#086FAD"><b>{model}</b></font><br/><font color="#5E707B">{area}</font><br/><br/>{body}',
               color=RED if i == 6 else BLUE, fill=LIGHTRED if i == 6 else WHITE, size=11.3)
        d.arrow([(x + 105, 588), (x + 105, 560)], head=False)
    d.arrow([(centers[0], 560), (centers[-1], 560)], head=False)
    d.text('Hasil fase + aturan bisnis', 60, 550, 210, 10.5, 13, MUTED)
    action_specs = [
        (48, 490, '5A  PENJUALAN DAN KEBUTUHAN',
         'Jika laku: stok berkurang; kas, omzet, HPP, laba dan PPN simulasi dicatat. Modal barang dan 50% laba kotor positif mendanai restok.<br/><br/>Jika stok kurang: transaksi ditutup; kebutuhan dicatat. Jika dana kurang: simpan restock_holds dan lanjutkan pelayanan.'),
        (570, 490, '5B  RFQ, NEGOSIASI, DAN PILIH VENDOR',
         'Restok 6-14 unit; periksa minimum faktur. Vendor membuka 110% harga katalog dan floor 90%; maksimal 3 ronde/vendor.<br/><br/>Tawar balik memakai rumus. Pilih harga terendah dari kesepakatan. Jika semua gagal: tunda 18 giliran.'),
        (1092, right - 1092, '5C  DANA, KIRIMAN, DAN FAKTUR',
         'Wajib: faktur &lt;=kas bebas-reserved, faktur &lt;=fund, pendapatan &gt;=1,15 x biaya. Cadangkan dana; kas belum dibayar.<br/><br/>Kemas - kirim - periksa barang. Hanya unit layak masuk stok. Faktur berbeda: tahan dan koreksi; cocok: bayar.'),
    ]
    for x, width, title, body in action_specs:
        d.arrow([(x + width / 2, 560), (x + width / 2, 530)])
        d.node(x, 375, width, 155, title, body, color=GREEN, fill=LIGHTGREEN, size=12)
    # Persisted state feeds the next tick, never the training pipeline.
    d.arrow([(right, 453), (right + 20, 453), (right + 20, 1014), (right, 1014)])
    d.text('Umpan balik: simpan state/event; baca lagi pada giliran berikutnya.',
           1092, 368, right - 1092, 10.5, 13, GREEN)

    d.strip(48, 325, right - 48, '6  PEMBELAJARAN OFFLINE DAN ARTEFAK - dijalankan terpisah dari siklus operasional')
    offline = [
        (48, 270, 'SUMBER DATA', '<b>CSV: 500 transaksi</b><br/>Filter Electronics: 146.<br/>Laptop 56, Monitor 45, Printer 45.<br/><br/>Katalog runtime: median harga dari seluruh 146 transaksi.'),
        (344, 360, 'SKENARIO DAN LABEL', '<b>Sumber: 100 latih / 23 validasi / 23 uji.</b><br/>Tiap split membuat katalog sendiri.<br/>1.600 contoh per agen per split.<br/>Label 0/1 dari domain.targets().<br/><br/>Data keputusan dibentuk sintetis; bukan label keputusan historis.'),
        (730, 450, 'LATIH, VALIDASI, DAN EVALUASI', '<b>7 agen x 9 kandidat = 63 classifier.</b><br/>LR, SVM, KNN memakai StandardScaler.<br/>Pemilihan global: maksimalkan total balanced accuracy validasi, dengan 7 algoritme utama berbeda.<br/><br/>Test mengukur hasil; tidak mengganti pilihan dari test.'),
        (1206, right - 1206, 'ARTEFAK DAN PEMAKAIAN', '<b>models.joblib:</b> 7 utama + 28 cadangan.<br/><b>metrics.json:</b> nama main, cadangan, dan skor.<br/><br/><b>A:</b> server memuat main dan katalog saat mulai. Cadangan tidak berpindah otomatis; tidak ada online learning.'),
    ]
    for i, (x, width, title, body) in enumerate(offline):
        d.node(x, 112, width, 187, title, body, fill=LIGHTBLUE, size=12)
        if i < 3:
            end = x + width
            d.arrow([(end, 207), (offline[i + 1][0], 207)], BLUE, True)
    d.badge('A', right - 20, 310)
    d.text('Hijau: data/aksi runtime dan umpan balik state. Biru putus-putus: pipeline offline. Peran pendukung, truk, pemeriksaan kerusakan, serta pencocokan faktur berjalan dari event/aturan.',
           48, 91, right - 48, 11, 14, MUTED)
    d.text('Rujukan: server.py:11-16,69-103,128-539; domain.py:14-85; train.py:26-113; finance.py:14-86; web/app.js:20-27.',
           48, 69, right - 48, 9, 11, MUTED)


def draw_workflow(report):
    report.page('Arsitektur detail: alur keputusan operasional',
                'Urutan bernomor menunjukkan lintasan utama. H1-H3 menunjukkan penahanan dan koreksi. Satu langkah browser memajukan satu fase.', landscape(A3))
    d = Diagram(report)
    for x, w, title in [(48, 310, 'PENJUALAN DAN STOK'), (410, 370, 'PENGADAAN DAN NEGOSIASI'), (820, 310, 'KEUANGAN DAN PEMENUHAN')]:
        d.strip(x, 680, w, title)
    sales = [
        ('01  PELANGGAN DATANG', 'CatBoost: Beli/Lewat.<br/>Minat beli memerlukan prediksi positif dan anggaran per unit yang cukup.'),
        ('02  PENJUALAN', 'Random Forest: Layani/Tunda.<br/>Jual jika minat, anggaran, stok dan model memenuhi. Stok kurang: tutup transaksi.'),
        ('03  PEMERIKSAAN STOK', 'Logistic Regression + aturan.<br/>Proyeksi permintaan memengaruhi restok. Stok &lt;=3 atau kekurangan stok juga memicu kebutuhan.'),
        ('04  PERMINTAAN RESTOK', 'Masukkan kebutuhan ke restock_requests.<br/>Layani antrean aktif terlebih dahulu; proses kebutuhan ketika giliran memungkinkan.'),
    ]
    procurement = [
        ('05  JUMLAH DAN DANA MINIMUM', 'Tentukan 6-14 unit; periksa minimum faktur termasuk PPN. Kurang dana: <b>H1</b>.'),
        ('06  PRIORITAS VENDOR', 'SVM mengurutkan vendor, lalu harga/nama.<br/><b>Semua vendor tetap dinegosiasikan.</b> Pembuka=110% katalog; floor=90%.'),
        ('07  LOOP MAKSIMAL 3 RONDE / VENDOR', 'Counter = min(ceiling, ask x (0,86 + 0,045 x ronde)).<br/>Gradient Boosting + floor/kapasitas: terima.<br/>KNN menyaring hasil setelah vendor menerima.'),
        ('08  BANDINGKAN KESEPAKATAN', 'Pilih harga minimum dari penawaran yang disepakati. Tidak ada kesepakatan: <b>H2</b>.<br/>Jika ada, teruskan vendor dan biaya ke Keuangan.'),
    ]
    fulfillment = [
        ('09  PERSETUJUAN DARI ATURAN', 'Faktur &lt;=kas bebas-reserved; &lt;=fund;<br/>pendapatan &gt;=1,15 x biaya.<br/><b>XGBoost hanya pembanding/log.</b> Kurang dana: H1.'),
        ('10  CADANGKAN, KEMAS, KIRIM', 'Fund berkurang; reserved=invoice.<br/><b>Kas belum keluar.</b><br/>Packing dan shipping mengikuti aturan fase.'),
        ('11  PENERIMAAN DAN CEK FAKTUR', 'Periksa jumlah/kondisi. Unit layak menambah stok; perbarui HPP rata-rata.<br/>Faktur tidak sesuai unit/harga: <b>H3</b>.'),
        ('12  BAYAR SETELAH COCOK', 'Kas berkurang; PPN masukan dicatat.<br/>Reserved=0. Selisih reservasi kembali ke fund. Kondisi baru disimpan ke SQLite.'),
    ]
    ys = [550, 435, 320, 205]
    for x, width, nodes in [(48, 310, sales), (410, 370, procurement), (820, 310, fulfillment)]:
        for i, ((title, body), y) in enumerate(zip(nodes, ys)):
            d.node(x, y, width, 90, title, body, size=10.7)
            if i < 3:
                d.arrow([(x + width / 2, y), (x + width / 2, ys[i + 1] + 90)])
    d.arrow([(358, 250), (384, 250), (384, 660), (595, 660), (595, 640)])
    d.arrow([(780, 250), (800, 250), (800, 660), (975, 660), (975, 640)])
    d.arrow([(975, 205), (975, 190), (30, 190), (30, 595), (48, 595)], width=1.2)
    d.label('State baru menjadi observasi siklus berikutnya', 366, 184, 370, GREEN, 10)
    exception_specs = [
        (48, 340, 'H1  DANA BELUM CUKUP', 'Simpan restock_holds; kembali melayani pelanggan.<br/>Saat antrean selesai, cek dana kembali. Jika cukup, lanjutkan pengadaan. Jika laba tidak memenuhi, beri jeda percobaan.'),
        (410, 370, 'H2  SEMUA VENDOR GAGAL SEPAKAT', 'Tunda restok produk selama 18 giliran.<br/>Sistem kembali ke pelayanan pelanggan, kemudian dapat mencoba pengadaan lagi setelah jeda.'),
        (802, 328, 'H3  FAKTUR TIDAK COCOK', 'Tahan pembayaran - vendor koreksi faktur - cek lagi.<br/>Bayar hanya jumlah layak jual dan nilai yang sesuai pesanan. Barang rusak tidak masuk stok jual.'),
    ]
    for x, width, title, body in exception_specs:
        d.node(x, 72, width, 100, title, body, color=RED, fill=LIGHTRED, size=10.3)
    d.text('Rujukan: server.py:128-469. Jalur utama memakai model + aturan; pengemasan, kiriman, inspeksi, kerusakan dan pembayaran merupakan fase aturan.',
           48, 61, 1094, 8.2, 10, MUTED)


def draw_training(report):
    report.page('Arsitektur detail: pipeline training dan test',
                'Transaksi sumber dipisahkan terlebih dahulu. Label skenario dihasilkan dari aturan, kemudian semua algoritme dibandingkan pada tiap peran.', landscape(A3))
    d = Diagram(report)
    top = [
        (48, 225, '01  CSV SUMBER', '500 transaksi, 9 kolom.<br/>Produk, kategori, harga, vendor, tanggal, jumlah, total, pembeli, dan ID.'),
        (300, 250, '02  FILTER ELECTRONICS', '146 transaksi: Laptop 56,<br/>Monitor 45, Printer 45.<br/>Hanya kategori ini dipakai.'),
        (577, 250, '03  URUTKAN SUMBER', 'Urut PurchaseDate, lalu ID.<br/>Pemisahan sumber secara kronologis; tidak mengacak transaksi antarbagian.'),
        (854, 288, '04  PISAHKAN SUMBER', '100 latih / 23 validasi / 23 uji.<br/>Katalog evaluasi terpisah per split; katalog runtime memakai seluruh 146.'),
    ]
    for i, (x, width, title, body) in enumerate(top):
        d.node(x, 600, width, 90, title, body, size=10.7)
        if i < 3:
            d.arrow([(x + width, 645), (top[i + 1][0], 645)], BLUE)
    d.arrow([(998, 600), (998, 580)], BLUE, head=False)
    d.arrow([(218, 580), (998, 580)], BLUE, head=False)
    split_specs = [
        (48, '05A  LATIH: 100 TRANSAKSI', '1 Jan - 12 Sep 2024', '42', 'Data untuk fit model.'),
        (425, '05B  VALIDASI: 23 TRANSAKSI', '13 Sep - 10 Nov 2024', '43', 'Data untuk memilih model.'),
        (802, '05C  TEST: 23 TRANSAKSI', '15 Nov - 30 Des 2024', '44', 'Data untuk evaluasi akhir.'),
    ]
    for x, title, dates, seed, purpose in split_specs:
        d.arrow([(x + 170, 580), (x + 170, 557)], BLUE)
        body = f'<b>{dates}; seed {seed}.</b><br/><br/>Katalog dari median harga dalam split.<br/>examples(): variasikan stok, permintaan, anggaran, kapasitas dan penawaran.<br/><br/><b>1.600 vektor per agen.</b><br/>targets(): label biner 0/1 dari aturan.<br/><br/>{purpose}'
        d.node(x, 350, 340, 207, title, body, fill=LIGHTBLUE, size=11.2)
        d.arrow([(x + 170, 350), (x + 170, 316)], BLUE)
    d.node(48, 184, 340, 132, '06  FIT: 7 AGEN x 9 KANDIDAT',
           '63 classifier dilatih hanya dari split latih.<br/>DT, RF, Extra Trees, GB, LR, SVM, KNN, CatBoost, XGBoost.<br/><br/>StandardScaler untuk LR/SVM/KNN berada dalam pipeline fit.', size=10.9)
    d.node(425, 184, 340, 132, '07  NILAI VALIDASI DAN PILIH',
           'Matriks balanced accuracy 7 x 9.<br/>Penugasan global memaksimalkan total skor dengan 7 algoritme utama berbeda.<br/><br/>Tambahkan 4 cadangan terbaik per agen berdasarkan validasi.', size=10.9)
    d.node(802, 184, 340, 132, '08  UKUR TEST TANPA MEMILIH ULANG',
           'Ukur akurasi dan balanced accuracy semua kandidat pada contoh test.<br/><br/>Hasil test tidak digunakan untuk mengganti penugasan utama yang dipilih melalui validasi.', size=10.9)
    d.arrow([(388, 250), (425, 250)], BLUE)
    d.arrow([(765, 250), (802, 250)], BLUE)
    d.arrow([(595, 184), (595, 160)], BLUE)
    d.arrow([(972, 184), (972, 160)], BLUE)
    d.node(48, 66, 1094, 94, '09  SIMPAN ARTEFAK DAN MUAT DI SERVER',
           '<b>models.joblib:</b> 35 model = 7 utama + 28 cadangan. <b>metrics.json:</b> main, daftar cadangan, skor, versi dan hash sumber.<br/>Server memanggil <b>main saja</b>; tidak ada voting cadangan, failover otomatis, atau pembelajaran online.<br/><b>Total:</b> 4.800 contoh/agen; 33.600 vektor berlabel untuk 7 agen. Angka ini bukan jumlah transaksi historis.', color=GREEN, fill=LIGHTGREEN, size=11)
    d.text('Rujukan: train.py:26-113; domain.py:51-85; data/metrics.json. Data test tetap berupa skenario sintetis, bukan keputusan perusahaan nyata yang telah diberi label.',
           48, 62, 1094, 8.3, 10, MUTED)
