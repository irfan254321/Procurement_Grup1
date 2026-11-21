from pathlib import Path
from xml.sax.saxutils import escape
import csv
import json
import hashlib
import math

from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, A3, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'output/pdf'
OUT.mkdir(parents=True, exist_ok=True)
PDF = OUT / 'BIZ_District_Arsitektur_Agen_dan_Dataset.pdf'
FONT = Path('C:/Windows/Fonts')
for name, filename in [('Calibri', 'calibri.ttf'), ('Calibri-Bold', 'calibrib.ttf'), ('Calibri-Italic', 'calibrii.ttf')]:
    pdfmetrics.registerFont(TTFont(name, str(FONT / filename)))
pdfmetrics.registerFont(TTFont('Cambria-Math', str(FONT / 'cambria.ttc'), subfontIndex=1))
pdfmetrics.registerFontFamily('Calibri', normal='Calibri', bold='Calibri-Bold', italic='Calibri-Italic', boldItalic='Calibri-Bold')

INK = colors.HexColor('#183444')
BLUE = colors.HexColor('#086FAD')
RED = colors.HexColor('#B33F48')
GREEN = colors.HexColor('#4F8A5C')
MUTED = colors.HexColor('#5E707B')
LINE = colors.HexColor('#D5DFE4')
PALE = colors.HexColor('#F0F5F7')
LIGHTBLUE = colors.HexColor('#EAF3F9')
WHITE = colors.white
REVISION_DATE = '19 November 2026'
styles = {
    'body': ParagraphStyle('body', fontName='Calibri', fontSize=10.6, leading=14.1, textColor=INK, spaceAfter=0),
    'small': ParagraphStyle('small', fontName='Calibri', fontSize=9, leading=11.7, textColor=MUTED),
    'tiny': ParagraphStyle('tiny', fontName='Calibri', fontSize=8, leading=10.2, textColor=MUTED),
    'table': ParagraphStyle('table', fontName='Calibri', fontSize=9.5, leading=12.1, textColor=INK),
    'th': ParagraphStyle('th', fontName='Calibri-Bold', fontSize=9.3, leading=11.8, textColor=WHITE),
    'formula': ParagraphStyle('formula', fontName='Cambria-Math', fontSize=12.5, leading=18, textColor=INK),
}


class Report:
    def __init__(self):
        self.c = canvas.Canvas(str(PDF), pagesize=A4, pageCompression=1)
        self.c.setTitle('BIZ District - Arsitektur, Agen, Model, dan Dataset')
        self.c.setAuthor('Dokumentasi proyek BIZ District')
        self.c.setSubject('Arsitektur aktual electronics, model supervised, alur bisnis dan data latih-uji')
        self.number = 0
        self.count = 19
        self.w, self.h = A4
        self.y = 0

    def page(self, title, subtitle='', size=A4):
        if self.number:
            self.c.showPage()
        self.number += 1
        self.w, self.h = size
        self.c.setPageSize(size)
        self.c.setFillColor(BLUE)
        self.c.rect(0, self.h - 9, self.w, 9, fill=1, stroke=0)
        self.c.setFillColor(MUTED)
        self.c.setFont('Calibri-Bold', 9)
        self.c.drawString(46, self.h - 35, 'BIZ DISTRICT  /  DOKUMENTASI SISTEM')
        self.c.setFont('Calibri', 9)
        self.c.drawRightString(self.w - 46, self.h - 35, REVISION_DATE)
        self.c.setStrokeColor(LINE)
        self.c.line(46, 43, self.w - 46, 43)
        self.c.setFillColor(MUTED)
        self.c.setFont('Calibri', 8.5)
        self.c.drawString(46, 29, 'electronics/  |  Implementasi yang tersedia saat dokumentasi dibuat')
        self.c.drawRightString(self.w - 46, 29, f'{self.number:02d} / {self.count:02d}')
        self.y = self.h - 68
        self.title(title)
        if subtitle:
            self.p(subtitle, 'small', after=13)
        key = f'page{self.number}'
        self.c.bookmarkPage(key)
        self.c.addOutlineEntry(title, key, 0)

    def title(self, text):
        style = ParagraphStyle('title', fontName='Calibri-Bold', fontSize=24, leading=27, textColor=INK)
        self.para(text, style, after=10)

    def para(self, text, style, after=7, x=46, width=None):
        width = width or self.w - 92
        p = Paragraph(text, style)
        _, height = p.wrap(width, self.h)
        if self.y - height < 60:
            raise ValueError(f'Overflow page {self.number}, y={self.y}, text={text[:90]}')
        p.drawOn(self.c, x, self.y - height)
        self.y -= height + after
        return height

    def p(self, text, style='body', after=7):
        return self.para(text, styles[style], after)

    def formula(self, text):
        self.para(text, styles['formula'], after=6, x=60, width=self.w - 106)

    def heading(self, text):
        self.y -= 5
        style = ParagraphStyle('h', fontName='Calibri-Bold', fontSize=13.2, leading=16, textColor=BLUE)
        self.para(text, style, after=6)

    def box(self, title, text, fill=LIGHTBLUE):
        width = self.w - 92
        ps = Paragraph(f'<b>{title}</b><br/>{text}', styles['body'])
        _, height = ps.wrap(width - 24, self.h)
        height += 22
        if self.y - height < 60:
            raise ValueError(f'Box overflow page {self.number}: {title}')
        self.c.setFillColor(fill)
        self.c.roundRect(46, self.y - height, width, height, 7, fill=1, stroke=0)
        self.c.setFillColor(BLUE)
        self.c.roundRect(46, self.y - height, 4, height, 2, fill=1, stroke=0)
        ps.drawOn(self.c, 58, self.y - height + 11)
        self.y -= height + 11

    def table(self, headers, rows, widths, small=False):
        style = styles['small'] if small else styles['table']
        data = [[Paragraph(str(v), styles['th']) for v in headers]]
        for row in rows:
            data.append([Paragraph(str(v), style) for v in row])
        table = Table(data, colWidths=widths, hAlign='LEFT')
        commands = [
            ('BACKGROUND', (0, 0), (-1, 0), BLUE),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 9),
            ('RIGHTPADDING', (0, 0), (-1, -1), 9),
            ('TOPPADDING', (0, 0), (-1, -1), 6.5 if small else 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6.5 if small else 8),
            ('LINEBELOW', (0, 0), (-1, 0), .5, BLUE),
        ]
        for index in range(1, len(data)):
            commands.append(('BACKGROUND', (0, index), (-1, index), PALE if index % 2 else WHITE))
            commands.append(('LINEBELOW', (0, index), (-1, index), .35, LINE))
        table.setStyle(TableStyle(commands))
        _, height = table.wrap(self.w - 92, self.h)
        if self.y - height < 60:
            raise ValueError(f'Table overflow page {self.number}: height={height}, y={self.y}')
        table.drawOn(self.c, 46, self.y - height)
        self.y -= height + 10

    def source(self, text):
        self.y -= 3
        self.p('Rujukan implementasi: ' + text, 'tiny', after=0)

    def model(self, number, role, model, concept, features, target, runtime, example, params):
        self.heading(f'{number}. {role} - {model}')
        self.p(concept, after=5)
        self.p('<b>Masukan:</b> ' + features + '<br/><b>Label latihan:</b> ' + target, after=5)
        self.p('<b>Pengaruh saat berjalan:</b> ' + runtime, after=5)
        self.p('<b>Contoh aturan:</b> ' + example, after=5)
        self.p('<b>Konfigurasi:</b> ' + params, 'small', after=10)


report = Report()
W = A4[0] - 92
metrics = json.loads((ROOT / 'electronics/data/metrics.json').read_text())
rows = list(csv.DictReader((ROOT / 'electronics/data/spend_analysis_dataset.csv').open(encoding='utf-8-sig', newline='')))
erows = sorted((r for r in rows if r['Category'] == 'Electronics'), key=lambda r: (r['PurchaseDate'], r['TransactionID']))

# 01 - Opening and reading map.
report.page('Arsitektur, agen, model,<br/>dan dataset', 'Panduan sistem BIZ District - PT. Biz Indonesia Market')
report.p('BIZ District menyimulasikan penjualan Laptop, Monitor, dan Printer yang terhubung dengan persediaan, pengadaan, negosiasi vendor, penerimaan barang, dan keuangan. Dokumen ini menjelaskan implementasi utama di folder <b>electronics/</b>.')
report.box('Cara membaca sistem', 'Ada <b>7 peran dengan model klasifikasi</b>, dijalankan oleh satu pengatur alur Python. Karakter petugas dan truk memperlihatkan pekerjaan dari hasil simulasi. Prediksi model bekerja bersama aturan bisnis; tidak semua keputusan diserahkan kepada model.')
report.heading('Peta isi')
report.table(['Halaman', 'Pembahasan'], [
    ['02', 'Ringkasan arsitektur mengikuti susunan gambar referensi'],
    ['03-05', 'Diagram detail: data/model/aturan, keputusan operasional, training/test'],
    ['06', 'Arti komponen, hubungan data, API, dan penyimpanan'],
    ['07', 'Alur kerja dari pelanggan datang sampai pembayaran vendor'],
    ['08-09', 'Agen di enam lantai dan aktivitas di luar gedung'],
    ['10', 'Dataset pembelian elektronik, pembagian latih-validasi-uji, dan label'],
    ['11', 'Proses training serta fungsi sembilan algoritme kandidat'],
    ['12-14', 'Pengaruh setiap model terhadap keputusan agen dan contohnya'],
    ['15', 'Hasil evaluasi, model cadangan, dan batas interpretasi'],
    ['16-17', 'Notasi bobot tujuh agen dan matriks pemilihan model'],
    ['18', 'Dataset pengiriman, penalti risiko, dan agen pengangkut'],
    ['19', 'Rujukan implementasi, dokumentasi algoritme, dan reproduksi'],
], [65, W - 65])
report.p('<b>Istilah:</b> agen = peran pengambilan keputusan; model = classifier terlatih; petugas = karakter pembagian kerja; giliran = satu langkah proses yang dipicu dari browser.', 'small')
report.p(f'Dokumen mengikuti kode dan artefak yang tersedia pada {REVISION_DATE}. Diagram disusun berdasarkan struktur referensi pengguna dan modul yang ada di proyek.', 'small')

# 02 - Architecture: vector graphics, inspired by the reference layout.
report.page('Arsitektur sistem BIZ District', '', landscape(A3))
c = report.c
PW, PH = report.w, report.h

def dtext(text, x, top, width, size=11, leading=14, color=INK, bold=False, align=0):
    sty = ParagraphStyle('diagram', fontName='Calibri-Bold' if bold else 'Calibri', fontSize=size,
                         leading=leading, textColor=color, alignment=align)
    p = Paragraph(text, sty)
    _, hh = p.wrap(width, 1000)
    p.drawOn(c, x, top - hh)
    return hh

def arrow(points, color=GREEN, dashed=False, width=1.8):
    c.saveState()
    c.setStrokeColor(color)
    c.setLineWidth(width)
    c.setDash(6, 4) if dashed else c.setDash()
    path = c.beginPath()
    path.moveTo(*points[0])
    for point in points[1:]:
        path.lineTo(*point)
    c.drawPath(path)
    c.setDash()
    ax, ay = points[-2]
    bx, by = points[-1]
    theta = math.atan2(by - ay, bx - ax)
    length = 8
    for turn in [-.48, .48]:
        c.line(bx, by, bx - length * math.cos(theta + turn), by - length * math.sin(theta + turn))
    c.restoreState()

def tab(x, y, width, text, color=BLUE):
    c.setFillColor(color)
    c.roundRect(x, y, width, 34, 3, fill=1, stroke=0)
    dtext(text, x + 7, y + 25, width - 14, 12.4, 14, WHITE, True, 1)

xs = [60, 228, 396, 594, 772, 960]
ws = [150, 150, 180, 160, 170, 160]
tab(60, 697, 150, 'PERSEPSI')
tab(228, 697, 526, 'PUSAT KEPUTUSAN / BRAIN')
tab(772, 697, 170, 'PEMBELAJARAN')
tab(960, 697, 160, 'AKSI DIGITAL')
c.setStrokeColor(INK)
c.setDash(7, 4)
c.setLineWidth(1.1)
c.roundRect(216, 245, 550, 410, 9, fill=0, stroke=1)
c.setDash()

content = [
    ('INPUT DAN FITUR', [
        ('Observasi simulasi', 'Pelanggan, stok, antrean, kebutuhan, penawaran, kas, anggaran, dan faktur.'),
        ('Katalog sumber', 'CSV produk/vendor dan harga acuan.'),
        ('Pemformatan input', 'State JSON diubah menjadi 3 atau 4 fitur numerik sesuai peran.'),
        ('Kontrol pengguna', 'Putar, jeda, langkah berikutnya, dan reset lewat browser.'),
    ]),
    ('BASIS PENGETAHUAN', [
        ('Katalog', 'Median harga produk dan harga tiap vendor.'),
        ('Model terlatih', 'models.joblib<br/>7 model utama dan 28 cadangan.'),
        ('Memori operasional', 'SQLite: world JSON, stok, dana, antrean, hasil, dan riwayat.'),
        ('Konfigurasi aturan', 'domain.py dan finance.py; ambang serta asumsi simulasi.'),
    ]),
    ('MESIN KEPUTUSAN', [
        ('Orkestrator terpusat', 'agent.step(): satu fase per giliran.'),
        ('Inferensi tujuh peran', 'Pembeli - CatBoost<br/>Penjual - Random Forest<br/>Stock - Logistic Regression<br/>Pengadaan - SVM<br/>Vendor - Gradient Boosting<br/>Negosiasi - KNN<br/>Keuangan - XGBoost'),
        ('Hasil', 'Prediksi kelas biner dipadukan dengan aturan, lalu dicatat sebagai event.'),
    ]),
    ('TUJUAN DAN KENDALA', [
        ('Pelayanan dan stok', 'Pelanggan mampu membeli; persediaan cukup; kebutuhan restok tercatat.'),
        ('Kesepakatan vendor', 'Harga memenuhi batas, kapasitas cukup, tawaran disepakati.'),
        ('Kelayakan keuangan', 'Kas dan anggaran cukup; proyeksi markup minimal 15% dari biaya.'),
        ('Pencocokan faktur', 'Bayar sesuai unit layak jual dan harga pesanan yang cocok.'),
    ]),
    ('TRAINING OFFLINE', [
        ('Persiapan data', '146 transaksi elektronik;<br/>100 latih / 23 validasi / 23 uji.'),
        ('Generator skenario', '1.600 contoh per agen per split; label dari aturan targets().'),
        ('Latih dan pilih', '9 kandidat per agen; pilih 7 model utama berbeda berdasarkan validasi.'),
        ('Simpan artefak', 'models.joblib + metrics.json. Training ulang dijalankan terpisah.'),
    ]),
    ('EKSEKUSI SIMULASI', [
        ('Aksi bisnis', 'Jual barang, ajukan restok, negosiasi, pilih vendor, dan cadangkan dana.'),
        ('Pemenuhan pesanan', 'Kemas, kirim, periksa barang, koreksi faktur, lalu bayar.'),
        ('Perubahan state', 'Stok, kas, pajak simulasi, antrean, dan riwayat diperbarui.'),
        ('Tampilan hasil', 'Distrik 3D, aktivitas lantai, tabel, grafik, dan laporan.'),
    ]),
]
for i, ((title, blocks), x, width) in enumerate(zip(content, xs, ws), 1):
    c.setStrokeColor(INK)
    c.setLineWidth(.9)
    c.setDash(4, 3)
    c.roundRect(x, 263, width, 387, 12, fill=0, stroke=1)
    c.setDash()
    c.setFillColor(RED)
    c.roundRect(x + 9, 604, width - 18, 35, 3, fill=1, stroke=0)
    dtext(title, x + 18, 628, width - 36, 10.6, 12, WHITE, True, 1)
    c.setFillColor(INK)
    c.circle(x + 11, 647, 12, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont('Calibri-Bold', 11)
    c.drawCentredString(x + 11, 643, str(i))
    yy = 586
    for j, (head, body) in enumerate(blocks):
        yy -= dtext(head, x + 12, yy, width - 24, 11.4, 14, BLUE, True) + 5
        yy -= dtext(body, x + 12, yy, width - 24, 10.6, 13.8) + 16
    if yy < 274:
        raise ValueError(f'Diagram module {i} overflow {yy}')

# Solid arrows show runtime flow. Dashed blue arrows are offline artifact loading.
for start, finish in [(210, 228), (378, 396), (576, 594)]:
    arrow([(start, 475), (finish, 475)])
arrow([(754, 292), (760, 292), (760, 253), (951, 253), (951, 475), (960, 475)])
c.setFillColor(WHITE)
c.rect(774, 246, 171, 17, fill=1, stroke=0)
dtext('Keputusan setelah pemeriksaan aturan', 775, 260, 167, 9.5, 12, MUTED, False, 1)
arrow([(855, 650), (855, 665), (486, 665), (486, 650)], BLUE, True)
c.setFillColor(WHITE)
c.rect(428, 658, 384, 16, fill=1, stroke=0)
dtext('Artefak hasil training dimuat saat server mulai', 437, 672, 365, 10, 12, BLUE, False, 1)
arrow([(1040, 650), (1040, 687), (135, 687), (135, 650)], GREEN, False)
c.setFillColor(WHITE)
c.rect(266, 680, 638, 15, fill=1, stroke=0)
dtext('Umpan balik operasional: state baru menjadi observasi giliran berikutnya', 280, 694, 610, 10.5, 13, GREEN, False, 1)

tab(60, 205, 1060, 'LAPIS INTERAKSI DAN LINGKUNGAN SIMULASI')
lower = [
    ('Browser dan API', 'HTTP lokal + JSON<br/>Perintah pengguna dan hasil'),
    ('Agen dan petugas', '6 lantai BIZ + 5 vendor<br/>Pelanggan dan petugas pendukung'),
    ('Memori / SQLite', 'Stok, kas, permintaan,<br/>reservasi, faktur, riwayat'),
    ('Lingkungan bisnis', 'Produk, rak, antrean, vendor,<br/>kiriman, penerimaan, pajak'),
]
for ix, (title, body) in enumerate(lower):
    xx = 60 + ix * 269
    c.setFillColor(PALE)
    c.roundRect(xx, 104, 253, 86, 7, fill=1, stroke=0)
    dtext(title, xx + 13, 175, 227, 12, 15, RED, True)
    dtext(body, xx + 13, 152, 227, 10.7, 14)
arrow([(135, 263), (135, 239)])
arrow([(1040, 263), (1040, 239)])
dtext('Garis hijau: proses/umpan balik runtime. Garis biru putus-putus: hubungan training offline. Pembaruan state tidak otomatis melatih ulang model.', 60, 87, 1060, 10.3, 13, MUTED)

from biz_architecture_detail import draw_detailed_pages
draw_detailed_pages(report)

# Architecture interpretation.
report.page('Bagaimana komponen terhubung', 'Penjelasan diagram dan batas tanggung jawab sistem')
report.table(['Komponen', 'Isi pada implementasi kita'], [
    ['1. Persepsi', 'Data numerik dari kondisi dunia: stok, kebutuhan, harga, kapasitas, kas, dan faktur. CSV dipakai untuk membentuk katalog dan acuan skenario.'],
    ['2. Pengetahuan', 'Katalog dalam memori, classifier tersimpan, serta world JSON di SQLite. State disimpan kembali setelah setiap aksi.'],
    ['3. Mesin keputusan', 'agent.step() memilih fase yang aktif, memanggil classifier terkait, menerapkan aturan, lalu mencatat event.'],
    ['4. Tujuan/kendala', 'Pelayanan pelanggan, ketersediaan barang, harga yang disepakati, dana memadai, serta kecocokan faktur. Batas ini tertulis dalam kode.'],
    ['5. Pembelajaran', 'train.py melatih dan mengevaluasi model sebelum aplikasi dipakai. Runtime membaca model utama yang sudah tersimpan.'],
    ['6. Aksi', 'Perubahan kondisi simulasi, transaksi, reservasi dana, kiriman dan pembayaran; hasilnya divisualisasikan di browser.'],
], [113, W - 113])
report.heading('Siklus satu giliran')
report.p('<b>Browser meminta langkah</b> melalui POST /api/step/{mode}. Server membuka transaksi SQLite, membaca world, menjalankan satu langkah, memperbarui ringkasan dana/grafik, menyimpan JSON, lalu mengirim kondisi baru. Browser menggambar aktivitas sesuai event terakhir.')
report.p('GET /api/world membaca kondisi aktif; GET /api/models mengambil peran dan metrik; POST /api/reset/{mode} membuat kondisi awal baru. Server yang dibuka kembali memakai database lokal yang sama.')
report.box('Makna umpan balik', 'Hasil penjualan atau pengadaan mengubah observasi giliran berikutnya. Umpan balik ini memperbarui <b>state operasional</b>. Pelatihan ulang dilakukan dengan menjalankan skrip training secara terpisah.')
report.p('Diagram mengadaptasi tata letak referensi, tetapi tidak menambahkan sensor fisik, LLM, knowledge graph, vector database, critic/reward RL, atau aktuator robot yang tidak tersedia dalam kode.', 'small')
report.source('[K1] agent.py:26-35, 69-103, 170-539; [K2] domain.py:9-47; [K4] train.py:70-113.')

# 04 - workflow.
report.page('Alur kerja dari awal sampai akhir', 'Penjualan menghasilkan kebutuhan; pengadaan memulihkan stok; faktur dibayar setelah cocok')
report.table(['Tahap', 'Proses dan hasil'], [
    ['01  Kedatangan', 'Sistem membuat 2-4 pelanggan. Setiap pelanggan membawa produk tujuan, jumlah 1-4 unit, dan anggaran. Model Pembeli menilai minat beli.'],
    ['02  Pelayanan', 'Penjual memeriksa minat, anggaran, stok, dan prediksi pelayanan. Pesanan yang kekurangan stok ditutup, kemudian kebutuhan barang dicatat.'],
    ['03  Penjualan', 'Jika berhasil: stok berkurang; kas, pendapatan, HPP, laba kotor dan PPN simulasi diperbarui. Modal barang terjual dan 50% laba kotor positif masuk dana restok.'],
    ['04  Pemeriksaan stok', 'Stock menilai stok dan permintaan. Permintaan restok dibuat bila diperlukan. Jumlah restok ditentukan aturan, umumnya 6-14 unit.'],
    ['05  Pengadaan', 'Dana minimum diperiksa. Jika cukup, vendor diprioritaskan dan dimintai penawaran. Seluruh kandidat tetap diperiksa.'],
    ['06  Negosiasi', 'Vendor membuka harga, pembeli menawar balik, vendor merespons. Maksimal 3 putaran tiap vendor; kesepakatan disaring oleh model Negosiasi.'],
    ['07  Pemilihan/dana', 'Pengadaan memilih kombinasi pemasok dan rute yang memenuhi kendala dengan biaya faktur dan penalti risiko terendah. Keuangan memeriksa dana dan proyeksi laba.'],
    ['08  Pemenuhan', 'Vendor mengemas, lalu pengangkut mengambil dan mengantar barang ke BIZ. Gudang memeriksa jumlah dan kondisi sebelum menambah stok.'],
    ['09  Pembayaran', 'Pesanan, penerimaan dan faktur dicocokkan. Selisih ditahan untuk koreksi. Saat cocok: kas dan PPN masukan dicatat, reservasi dilepas.'],
], [104, W - 104], small=True)
report.heading('Ketika proses belum bisa dilanjutkan')
report.p('<b>Dana kurang</b> menahan permintaan di restock_holds sampai dana cukup. <b>Tanpa rencana yang memenuhi kapasitas, tenggat, dan target laba</b>, restok ditunda 18 giliran. <b>Stok kurang saat penjualan</b> menutup transaksi pelanggan dan mencatat kebutuhan barang.', 'small')
report.source('[K1] agent.py:128-469; [K3] finance.py:14-53.')

# 05 - floors.
report.page('Agen di dalam enam lantai BIZ', 'Model memberi prediksi; karakter pendukung memperlihatkan pembagian pekerjaan')
report.table(['Area', 'Agen/peran utama', 'Petugas dan kegunaannya'], [
    ['Lantai 1<br/><b>Lobi</b>', '<b>Pembeli / CatBoost</b><br/>Keputusan minat beli melekat pada pelanggan.', '<b>Resepsionis:</b> mencatat kedatangan dan mengarahkan pelanggan.<br/><b>Konsultasi Produk:</b> membantu memahami pilihan Laptop, Monitor, dan Printer.'],
    ['Lantai 2<br/><b>Toko</b>', '<b>Penjual / Random Forest</b><br/>Menilai apakah pesanan dapat dilayani.', '<b>Penjual:</b> meninjau pesanan.<br/><b>Penyiapan Barang:</b> mengambil/membawa barang.<br/><b>Kasir:</b> memindai barang dan mencetak struk.'],
    ['Lantai 3<br/><b>Gudang</b>', '<b>Stock / Logistic Regression</b><br/>Membantu menentukan kebutuhan restok.', '<b>Stock:</b> memeriksa persediaan.<br/><b>Penerimaan Gudang:</b> memeriksa jumlah dan kondisi.<br/><b>Penataan Gudang:</b> menata unit layak jual.'],
    ['Lantai 4<br/><b>Keuangan</b>', '<b>Keuangan / XGBoost</b><br/>Prediksi kelayakan sebagai pembanding perhitungan.', '<b>Keuangan:</b> memeriksa kelayakan.<br/><b>Anggaran:</b> memantau pagu dan pencadangan.<br/><b>Pembayaran:</b> mencocokkan dan membayar faktur.'],
    ['Lantai 5<br/><b>Pengadaan</b>', '<b>Pengadaan / SVM</b><br/>Memprioritaskan urutan vendor.', '<b>Pengadaan:</b> mengirim permintaan harga.<br/><b>Analisis Vendor:</b> membandingkan hasil penawaran.<br/><b>Pembelian:</b> menyiapkan rincian jumlah pesanan.'],
    ['Lantai 6<br/><b>Negosiasi</b>', '<b>Negosiasi / KNN</b><br/>Menyaring kesepakatan akhir.', '<b>Negosiasi:</b> bertukar tawaran.<br/><b>Pencatat Negosiasi:</b> mencatat nilai dan hasil.<br/><b>Perwakilan Vendor:</b> tamu saat pembicaraan berlangsung.'],
], [73, 154, W - 227])
report.box('Arti label "agent" pada petugas', 'Kasir, resepsionis, penerimaan, penataan, anggaran, pencatat, dan pengiriman belum memiliki model ML terpisah. Tugas mereka dipicu event dari server. Model Pembeli digunakan oleh pelanggan, bukan staf resepsionis.')
report.source('[K5] web/app.js:20-27; [K6] web/interiors.js:1-22, 62-90, 234-244; [K7] web/room-jobs.js:1-119.')

# 06 - outside + arrival scenario.
report.page('Agen dan aktivitas di luar gedung', 'Vendor, pelanggan, dan pengiriman terhubung ke kondisi dunia yang sama')
report.table(['Elemen', 'Kegunaan dan hubungan dengan model'], [
    ['Lima perusahaan vendor', 'CloudSoft Corp.; FurniWorks Ltd.; OfficeSupplies Co.; QuickDeliver Ltd.; TechMart Inc. Harga per produk berasal dari katalog. Semua memakai model <b>Vendor / Gradient Boosting</b> yang sama dengan input berbeda.'],
    ['Petugas kantor vendor', '<b>Agent Vendor</b> meninjau tawaran dan mengirim faktur koreksi. <b>Pengiriman Vendor</b> menyiapkan kardus dan membawa barang ke area muat.'],
    ['Perwakilan vendor', 'Karakter tamu muncul di ruang negosiasi untuk vendor yang sedang dibahas. Keputusan penerimaan tetap memakai peran Vendor.'],
    ['Pelanggan di jalan/lobi', 'Karakter mewakili event kedatangan dan antrean. Minat belinya diprediksi CatBoost; pilihan jumlah dan anggaran dibentuk oleh simulasi.'],
    ['Pengangkut dan truk', '<b>Agent Dispatch</b> memeriksa rencana muatan, rute, dan jadwal. <b>Agent Angkut</b> mengambil barang di vendor dan mengantar ke BIZ. Dijkstra menghitung rute; animasi mengikuti kiriman yang dipilih.'],
], [116, W - 116])
report.heading('Contoh kiriman rusak: pesan 10, terima layak 8')
report.p('Untuk contoh dengan ongkir nol dan harga Rp1.000.000 per unit, pembelian 10 unit memiliki biaya dasar Rp10.000.000 dan faktur Rp11.100.000 dengan PPN simulasi 11%. Dana itu dicadangkan setelah pembelian disetujui.')
report.p('Jika 2 unit rusak, hanya 8 unit masuk stok. Faktur untuk 10 unit ditahan. Vendor menerbitkan faktur pengganti Rp8.880.000 untuk 8 unit, terdiri dari biaya Rp8.000.000 dan PPN Rp880.000. Setelah cocok, Keuangan membayar dan mengembalikan selisih reservasi Rp2.220.000 ke dana restok.')
report.p('Contoh angka di atas menjelaskan aturan, bukan kutipan satu transaksi historis. Skenario damage memunculkan dua unit rusak pada kiriman pertama. Mode auto juga dapat menimbulkan kerusakan secara acak; belum ada model prediksi kerusakan.', 'small')
report.source('[K1] agent.py:398-469; [K6] web/interiors.js:68-74; [K8] web/district-3d.mjs:105-147.')

# 07 - dataset.
report.page('Dataset pembelian elektronik', 'Transaksi sumber dipakai sebagai acuan untuk membentuk contoh keputusan berlabel')
report.p('File lokal <b>electronics/data/spend_analysis_dataset.csv</b> berisi <b>500 transaksi dan 9 kolom</b>. Dokumentasi proyek mengatribusikan sumbernya ke <b>Company Purchasing Dataset oleh Shahriar Kabir di Kaggle</b> [D1]. Hanya kategori Electronics dipakai: <b>146 transaksi</b>, yaitu Laptop 56, Monitor 45, dan Printer 45.')
report.p('<b>Kolom:</b> TransactionID, ItemName, Category, Quantity, UnitPrice, TotalCost, PurchaseDate, Supplier, dan Buyer.', 'small')
report.heading('Pembagian kronologis sebelum pembentukan skenario')
report.table(['Bagian', 'Sumber', 'Tanggal transaksi', 'Contoh/agen'], [
    ['Latih', '100', '1 Jan - 12 Sep 2024', '1.600'],
    ['Validasi', '23', '13 Sep - 10 Nov 2024', '1.600'],
    ['Uji / test', '23', '15 Nov - 30 Des 2024', '1.600'],
], [79, 60, 195, W - 334])
report.p('Transaksi diurutkan menurut PurchaseDate, lalu TransactionID. Tiap bagian membentuk katalog sendiri. Harga acuan/vendor diambil dari median harga; stok, permintaan, anggaran, kapasitas, dan penawaran divariasikan secara sintetis. Seed latih/validasi/uji adalah 42/43/44.')
report.box('Jumlah data yang benar', 'Per agen: <b>1.600 latih + 1.600 validasi + 1.600 uji = 4.800 contoh</b>. Untuk tujuh agen: <b>33.600 vektor berlabel</b>. Angka itu bukan 33.600 transaksi historis. Fitur Stock bahkan dibentuk dari angka acak stok, permintaan, dan titik pesan.')
report.heading('Dari mana label keputusan berasal?')
report.table(['Agen', 'Aturan label positif / kelas 1'], [
    ['Pembeli', 'Harga &lt;= anggaran pelanggan.'],
    ['Penjual', 'Stok &gt;= permintaan.'],
    ['Stock', 'Stok - permintaan &lt;= titik pesan.'],
    ['Pengadaan', 'Penawaran &lt;= 108% harga acuan; kapasitas &gt;= kebutuhan.'],
    ['Vendor', 'Tawaran &gt;= harga minimum; jumlah &lt;= kapasitas.'],
    ['Negosiasi', 'Harga minimum &lt;= tawaran &lt;= batas pembeli.'],
    ['Keuangan', 'Biaya termasuk PPN &lt;= dana; pendapatan &gt;= 115% biaya.'],
], [90, W - 90], small=True)
report.source('[K2] domain.py:51-85; [K4] train.py:41-74; [D1] CSV lokal dan README dataset.')

# 08 - nine algorithms.
report.page('Training dan fungsi sembilan algoritme', 'Setiap algoritme dibandingkan pada semua tujuh peran')
report.p('Prosesnya: <b>pisahkan sumber - buat fitur/label - latih 9 kandidat per agen - ukur validasi - pilih model utama - ukur test - simpan artefak</b>. Total ada 63 kandidat terlatih. Logistic Regression, SVM, dan KNN memakai StandardScaler yang dilatih dalam pipeline.')
report.table(['Algoritme', 'Bagaimana mengambil keputusan', 'Peran utama terpilih'], [
    ['Decision Tree', 'Satu pohon memisahkan fitur melalui ambang sampai memperoleh kelas. Pembanding yang mudah ditelusuri.', 'Tidak menjadi utama'],
    ['Random Forest', 'Banyak pohon dengan variasi data/fitur; probabilitas kelas digabungkan untuk menentukan prediksi.', 'Penjual'],
    ['Extra Trees', 'Ensemble pohon dengan kandidat ambang pemisahan lebih acak. Alternatif pembanding/cadangan.', 'Tidak menjadi utama'],
    ['Gradient Boosting', 'Pohon ditambahkan bertahap untuk memperbaiki kesalahan prediksi gabungan sebelumnya.', 'Vendor'],
    ['Logistic Regression', 'Kombinasi berbobot fitur menghasilkan probabilitas dan kelas. Di sini dipakai untuk klasifikasi biner.', 'Stock'],
    ['SVM / SVC', 'Mempelajari batas pemisah kelas dengan margin dan support vectors; kernel menangani pola nonlinier.', 'Pengadaan'],
    ['KNN', 'Mengklasifikasikan keadaan baru dari suara 19 contoh latihan terdekat setelah penskalaan fitur.', 'Negosiasi'],
    ['CatBoost', 'Boosting pohon untuk data tabular. Pembeli memakai fitur numerik. Model risiko pengiriman juga memakai fitur kategoris dari dataset kedua.', 'Pembeli'],
    ['XGBoost', 'Boosting pohon yang mengoptimalkan kesalahan prediksi dan regularisasi kompleksitas model.', 'Keuangan'],
], [100, 288, W - 388], small=True)
report.box('Mengapa setiap agen memakai algoritme berbeda?', 'Pemilihan memaksimalkan <b>total balanced accuracy validasi</b> dengan syarat tujuh algoritme utama tidak berulang. Jadi model utama tidak selalu memiliki skor tertinggi untuk agennya secara individual. Penugasan ini adalah pilihan eksperimen proyek, bukan sifat wajib masing-masing algoritme.')
report.p('Empat cadangan per peran juga disimpan, sehingga artefak memuat 35 model. Saat berjalan, server hanya memanggil model main. Tidak ada voting antarmodel cadangan atau perpindahan otomatis ke cadangan.', 'small')
report.source('[K4] train.py:26-38, 76-108; [K1] agent.py:69-72. Definisi algoritme: [A1]-[A7].')

# 09 - three agents.
report.page('Model untuk pelanggan, toko, dan stok', 'Masukan model adalah angka; kelas keluarannya disaring oleh kondisi bisnis')
report.model('1', 'Pembeli', 'CatBoost',
    'Boosting pohon mempelajari hubungan harga dan kemampuan bayar. Keluaran runtime adalah kelas Beli/Lewat, bukan jawaban percakapan.',
    'Harga jual per unit (termasuk PPN saat runtime), kesediaan bayar per unit, jumlah unit.',
    'Beli jika harga &lt;= anggaran.',
    'Prediksi Beli dan anggaran yang cukup membentuk minat beli pelanggan. Pelanggan tetap harus melewati pemeriksaan stok oleh Penjual.',
    'Harga Rp1.110.000 dan anggaran Rp1.200.000 memenuhi aturan beli; jika anggaran Rp1.000.000, pembelian diblok oleh batas anggaran.',
    '120 iterasi, depth 5; random seed 42.')
report.model('2', 'Penjual', 'Random Forest',
    'Sekumpulan pohon menilai kemampuan pelayanan. Agregasi prediksi mengurangi ketergantungan pada satu pohon.',
    'Stok tersedia, jumlah permintaan, harga jual dasar per unit.',
    'Layani jika stok &gt;= jumlah permintaan.',
    'Prediksi Layani menjadi salah satu syarat penjualan, bersama minat beli, anggaran pelanggan, dan stok nyata yang cukup.',
    'Stok 5 dan pesanan 3 memenuhi batas persediaan. Stok 2 untuk pesanan 3 tetap gagal walaupun model menghasilkan Layani.',
    '80 pohon, max_depth 9, min_samples_leaf 5; seed 42.')
report.model('3', 'Stock', 'Logistic Regression',
    'Classifier mempelajari batas dari kombinasi berbobot stok, permintaan dan titik pesan. Nama regresi di sini tetap menghasilkan kelas biner.',
    'Stok, permintaan tercatat, titik pesan (runtime: 3).',
    'Restok perlu jika stok - permintaan &lt;= titik pesan.',
    'Model memengaruhi kebutuhan mendatang saat permintaan positif. Stok &lt;=3 atau kekurangan stok dapat memicu restok langsung melalui aturan.',
    'Stok 8, permintaan 6, titik pesan 3 memberi sisa proyeksi 2 sehingga labelnya Restok perlu. Pelaksanaan tetap menunggu dana dan giliran.',
    'StandardScaler + LogisticRegression; pengaturan classifier lainnya default.')
report.source('[K2] domain.py:22-29, 72-82; [K1] agent.py:128-144, 206-275; [K4] train.py:26-65.')

# 10 - three agents.
report.page('Model untuk pengadaan dan negosiasi', 'Memisahkan prioritas, respons vendor, dan penyaringan kesepakatan')
report.model('4', 'Pengadaan', 'SVM',
    'SVC mempelajari batas antara vendor berlabel Prioritas dan Bandingkan. Kernel RBF default dapat membentuk batas nonlinier setelah penskalaan.',
    'Harga penawaran vendor, harga acuan produk, kapasitas vendor, kebutuhan unit.',
    'Prioritas jika penawaran &lt;=108% acuan dan kapasitas mencukupi.',
    'Vendor diurutkan menurut prioritas model, harga, lalu nama. Setelah negosiasi, pengalokasi membandingkan kombinasi pemasok dan rute berdasarkan biaya, risiko, dan kendala.',
    'Penawaran 105 saat acuan 100 dan kapasitas 20 untuk kebutuhan 10 memenuhi label prioritas. SVM tidak menentukan harga tawar ataupun pemenang akhir.',
    'StandardScaler + SVC; kernel RBF, C=1, gamma=scale (default).')
report.model('5', 'Vendor', 'Gradient Boosting',
    'Pohon ditambahkan bertahap untuk memperbaiki kesalahan klasifikasi respons tawaran. Lima perusahaan berbagi model role Vendor yang sama.',
    'Tawaran pembeli, harga minimum vendor, jumlah pesanan, kapasitas.',
    'Terima jika tawaran &gt;= harga minimum dan jumlah &lt;= kapasitas.',
    'Pada vendor_reply, Terima hanya berlaku jika model positif dan dua batas harga/kapasitas juga terpenuhi. Prediksi saat pembukaan hanya dicatat.',
    'Tawaran 95, floor 90, pesanan 10, kapasitas 20 memenuhi batas. Tawaran 85 selalu ditolak oleh batas minimum walau prediksi berbeda.',
    'GradientBoostingClassifier, max_depth 3, seed 42; 100 tahap default.')
report.model('6', 'Negosiasi', 'KNN',
    'Model mencari 19 contoh latihan terdekat dan mengambil kelas mayoritas. Skala harga diseimbangkan melalui StandardScaler.',
    'Harga tawaran/kesepakatan, batas pembeli, harga minimum vendor.',
    'Sepakat jika floor &lt;= harga &lt;= batas pembeli.',
    'Pada vendor_result, menjadi syarat kesepakatan setelah vendor menerima. Pada counter, prediksi hanya dicatat; nilai tawar berasal dari rumus.',
    'Floor 90, harga 95, batas pembeli 100 berada dalam rentang label Sepakat. KNN tidak menghitung nominal 95 itu.',
    'StandardScaler + KNeighborsClassifier(n_neighbors=19).')
report.source('[K1] agent.py:276-356; [K2] domain.py:22-29, 82-85; [K4] train.py:26-38.')

# 11 - finance and explicit business controls.
report.page('Model keuangan dan aturan persetujuan', 'Prediksi kelayakan dibandingkan dengan perhitungan yang dapat ditelusuri')
report.model('7', 'Keuangan', 'XGBoost',
    'Boosting pohon memprediksi Layak/Tahan dari contoh biaya, dana, dan pendapatan. Keluaran ini dipakai sebagai pembanding dan dicatat dalam event.',
    'Biaya pengadaan sebelum PPN, dana tersedia untuk restok, potensi pendapatan sebelum PPN.',
    'Layak jika biaya termasuk PPN &lt;= dana dan pendapatan &gt;=115% biaya.',
    '<b>Persetujuan akhir dihitung oleh aturan.</b> Jika model berbeda dari hitungan, perbedaan ditulis pada riwayat dan keputusan tetap memakai hitungan.',
    'Biaya 100, faktur 111, dana 120, pendapatan 120 memenuhi aturan. Dana 105 tidak cukup untuk faktur 111 walau prediksi model Layak.',
    '100 pohon, max_depth 4, learning_rate 0,1, seed 42.')
report.heading('Tiga syarat wajib saat persetujuan')
report.table(['Pemeriksaan', 'Aturan yang digunakan'], [
    ['Kas bebas', 'Faktur termasuk PPN &lt;= kas bebas - dana yang sudah dicadangkan. Kas bebas sudah memperhitungkan gaji, operasional, cadangan, dan kewajiban pajak simulasi.'],
    ['Pagu pengadaan', 'Faktur termasuk PPN &lt;= sisa anggaran pengadaan (fund).'],
    ['Proyeksi laba', 'Pendapatan jika seluruh unit terjual &gt;= 1,15 x biaya dasar pembelian. Ini markup 15% terhadap biaya, bukan margin 15% terhadap pendapatan.'],
], [112, W - 112])
report.heading('Pencadangan, penerimaan, dan pembayaran')
report.p('Ketika pembelian disetujui, fund berkurang dan reserved bertambah; kas belum dibayar ke vendor. Setelah barang diperiksa, faktur dicocokkan dengan jumlah layak jual. Saat cocok, kas berkurang, PPN masukan dicatat, reserved dilepas, dan selisih faktur koreksi kembali ke fund.')
report.p('Sistem juga mencatat pendapatan, HPP, laba kotor, saldo kas, dan pajak simulasi. PPN 11% adalah asumsi yang dipakai kode. Tagihan pajak lain dimasukkan melalui formulir; pencatatan ini tidak mengirim pembayaran ke bank atau instansi pajak.', 'small')
report.source('[K1] agent.py:147-148, 357-469; [K3] finance.py:14-86; [K4] train.py:37.')

# 12 - metrics/backups/limits.
report.page('Evaluasi dan batas pembacaan hasil', 'Skor di bawah berasal dari metrics.json yang disertakan di proyek')
agent_names = {'buyer': 'Pembeli', 'seller': 'Penjual', 'stock': 'Stock', 'procurement': 'Pengadaan', 'vendor': 'Vendor', 'deal': 'Negosiasi', 'finance': 'Keuangan'}
order = list(agent_names)
fmt = lambda x: f'{100*x:.2f}%'.replace('.', ',')
score_rows = []
for role in order:
    value = metrics['agents'][role]
    score = value['candidates'][value['main']]
    score_rows.append([agent_names[role], value['main'], fmt(score['validation']), fmt(score['accuracy']), fmt(score['balanced'])])
report.table(['Agen', 'Model utama', 'Validasi BA', 'Test akurasi', 'Test BA'], score_rows, [74, 129, 97, 100, W - 400], small=True)
report.p('<b>BA (balanced accuracy)</b> adalah rata-rata recall kedua kelas. Akurasi biasa adalah proporsi seluruh prediksi yang benar. Masing-masing agen diuji pada 1.600 contoh sintetis. Skor validasi dipakai untuk pemilihan; test untuk evaluasi akhir.', 'small')
report.heading('Empat model cadangan yang disimpan per agen')
report.table(['Agen', 'Cadangan menurut urutan validasi'], [[agent_names[role], ', '.join(metrics['agents'][role]['selected'][1:])] for role in order], [82, W - 82], small=True)
report.heading('Batas interpretasi')
report.p('<b>Label berasal dari aturan.</b> Skor tinggi menunjukkan kemampuan meniru aturan pada generator skenario yang digunakan. Hasil ini belum membuktikan keberhasilan negosiasi bisnis nyata atau generalisasi ke kondisi perusahaan lain.', 'small')
report.p('<b>Pemisahan sumber dilakukan berdasarkan waktu.</b> Namun test tetap berisi skenario sintetis, bukan transaksi riil berlabel keputusan. Katalog runtime memakai seluruh 146 transaksi; katalog evaluasi dibuat terpisah per split.', 'small')
report.p('<b>Penugasan algoritme dibatasi harus berbeda.</b> Model utama tidak selalu yang tertinggi secara individual. Tidak ada training online, prediksi kerusakan terlatih, atau pergantian otomatis ke model cadangan.', 'small')
report.source('[K4] train.py:70-108; [K9] data/metrics.json. Angka dibulatkan dua desimal.')

# 16 - model weights for the first four roles.
report.page('Notasi bobot model per agen', 'Pembeli, Penjual, Stock, dan Keuangan')
report.p('Pelatihan model keputusan memakai contoh berlabel dari dataset pembelian elektronik. Kode memanggil <b>fit(X, y)</b> dengan bobot sampel bawaan. Bobot di bawah menggambarkan cara setiap model menggabungkan fiturnya, pohonnya, atau contoh latihnya.')
report.p('Pada rumus ini, x adalah fitur masukan, h<sub>t</sub>(x) adalah kontribusi pohon ke-t, dan σ(u) = 1 / (1 + exp(−u)) adalah fungsi sigmoid. Pada Stock, SVM, dan KNN, StandardScaler menghitung z<sub>j</sub> = (x<sub>j</sub> − μ<sub>j</sub>) / s<sub>j</sub> dari rata-rata μ<sub>j</sub> dan simpangan baku s<sub>j</sub> data latih.')

report.heading('1. Agent Pembeli | CatBoost')
report.formula('s(x) = σ(∑<sub>t=1…120</sub> h<sub>t</sub>(x))')
report.p('Kontribusi 120 pohon dijumlahkan untuk memberi skor minat beli dari harga, kesediaan bayar, dan jumlah. Pembelian dilanjutkan jika model memprediksi Beli dan anggaran cukup untuk harga termasuk PPN.')

report.heading('2. Agent Penjual | Random Forest')
report.formula('s(x) = (1 / 80) × ∑<sub>t=1…80</sub> p<sub>t</sub>(x)')
report.p('p<sub>t</sub>(x) adalah probabilitas kelas Layani dari pohon ke-t. Masing-masing pohon berbobot 1/80. Penjualan terjadi jika model memprediksi Layani, pelanggan bersedia membeli, dan stok mencukupi.')

report.heading('3. Agent Stock | Logistic Regression')
report.formula('s(z) ≈ σ(−0,582 − 7,954z<sub>stok</sub> + 4,926z<sub>permintaan</sub> + 1,352z<sub>titik pesan</sub>)')
report.p('Stok lebih tinggi menurunkan skor restok. Permintaan dan titik pesan yang lebih tinggi menaikkannya. Pada simulasi, stok paling banyak 3 unit atau pesanan yang kekurangan stok juga memicu kebutuhan restok.')
report.p('Koefisien diambil dari model tersimpan dan dibulatkan ke tiga desimal. Dalam urutan fitur di atas, rata-rata latihnya 14,486 / 9,306 / 3,961 dan simpangan bakunya 8,774 / 5,393 / 1,419.', 'small')

report.heading('4. Agent Keuangan | XGBoost')
report.formula('s(x) = σ(b + ∑<sub>t=1…100</sub> h<sub>t</sub>(x))')
report.p('Model memakai 100 pohon dengan laju belajar 0,1. Kontribusi pohon yang tersimpan sudah memuat penskalaan ini. Skor menjadi pembanding untuk aturan akhir yang memeriksa kas bebas setelah cadangan, anggaran, dan pendapatan minimal 1,15 kali biaya pengadaan.')
report.source('[K1] agent.py:122-136, 189-202, 269-335, 455-473; [K4] train.py:26-38; [K10] model tersimpan.')

# 17 - remaining model weights and model assignment.
report.page('Notasi bobot pengadaan dan vendor', 'Pengadaan, Vendor, Negosiasi, dan pemilihan model utama')
report.heading('5. Agent Pengadaan | SVM dengan kernel RBF')
report.formula('f(z) ≈ −1,296 + ∑<sub>i=1…840</sub> β<sub>i</sub> exp(−0,25 ‖z − z<sub>i</sub>‖<super>2</super>)')
report.p('β<sub>i</sub> adalah bobot bertanda untuk support vector z<sub>i</sub>. Model tersimpan memakai 840 support vector dan γ ≈ 0,25. Tanda skor menentukan kelas Prioritas atau Bandingkan untuk urutan permintaan penawaran. Harga menjadi pembanding berikutnya.')

report.heading('6. Agent Vendor | Gradient Boosting')
report.formula('s(x) = σ(b + 0,1 × ∑<sub>t=1…100</sub> h<sub>t</sub>(x))')
report.p('Setiap pohon koreksi dikalikan laju belajar 0,1. Kelima pemasok memakai model respons tawaran ini. Tawaran diterima jika prediksi positif, harga mencapai batas minimum vendor, dan jumlah pesanan masih dalam kapasitas.')

report.heading('7. Agent Negosiasi | KNN')
report.formula('s(z) = (1 / 19) × ∑<sub>i ∈ N19(z)</sub> y<sub>i</sub>')
report.p('N<sub>19</sub>(z) adalah 19 contoh latih terdekat menurut jarak Euclidean setelah standardisasi. Masing-masing punya satu suara dengan bobot 1/19. Kelas Sepakat memerlukan minimal 10 suara, dan hasil ini dipakai setelah vendor menerima tawaran.')

report.heading('Matriks bobot untuk penugasan model')
report.p('Saat pelatihan, setiap pasangan agen a dan model kandidat m memperoleh bobot W<sub>a,m</sub> dari akurasi seimbang pada data validasi. Ukuran ini merata-ratakan kemampuan mengenali kelas positif dan kelas negatif.')
report.formula('W<sub>a,m</sub> = ½ × [TP / (TP + FN) + TN / (TN + FP)]')
report.formula('Maksimalkan ∑<sub>a</sub> W<sub>a,m(a)</sub>, dengan m(a) berbeda untuk setiap agen.')
report.p('TP dan TN menghitung prediksi benar untuk kelas positif dan negatif. FN dan FP menghitung kasus yang keliru. Pengujian kemudian mengukur model terpilih pada bagian uji yang terpisah.', 'small')
report.source('[K1] agent.py:339-356, 384-407; [K4] train.py:26-38, 74-105; [K10] model tersimpan.')

# 18 - second dataset and shared logistics scoring.
report.page('Bobot risiko pemasok dan rute', 'Dataset pengiriman, optimasi alokasi, dan pemakaian oleh agen pengangkut')
report.p('<b>Supply Chain Shipment Pricing Data</b> [D2] tersimpan sebagai <b>SCMS_Delivery_History_Dataset.csv</b>. Pembagian kronologis per pesanan menghasilkan <b>2.624 baris latih, 503 validasi, dan 1.149 uji</b>. Kelima vendor simulasi memakai satu CatBoost dengan profil dari riwayat pengiriman komoditas kesehatan.')

report.heading('Skor keterlambatan pemasok | CatBoost')
report.formula('y = 1 jika tanggal tiba aktual &gt; tanggal terjadwal, dan 0 jika tidak.')
report.formula('r(x) = σ(∑<sub>t=1…260</sub> h<sub>t</sub>(x))')
report.p('Model dilatih dengan Logloss dan laju belajar 0,055. Artefak melaporkan <b>class_weights = null</b>. Kode memberi label risiko tinggi pada r(x) ≥ 0,06. Nilai r(x) adalah skor historis dengan status kalibrasi <b>false</b> untuk penerapannya pada pemasok elektronik.')
report.p('Jadwal historis menjadi dasar waktu tempuh. Pada validasi, galat absolut rata-ratanya 0,44 hari, dibanding 1,34 hari untuk jadwal yang dikoreksi oleh regresi CatBoost.', 'small')

report.heading('Agent Pengadaan | Penalti risiko dalam alokasi')
report.formula('Penalti<sub>i</sub> = 0,15 × q<sub>i</sub> × p<sub>i</sub> × r<sub>i</sub>')
report.formula('Pilih rencana yang meminimalkan ∑<sub>i</sub> (I<sub>i</sub> + Penalti<sub>i</sub>).')
report.p('Untuk kiriman i, q adalah jumlah unit, p harga satuan, r skor risiko, dan I faktur berisi nilai barang, ongkir, dan PPN. Pengalokasi memakai skor kontinu r dan memeriksa jumlah pesanan, kapasitas, tenggat, anggaran, serta batas biaya.')
report.box('Contoh perhitungan', 'Nilai barang Rp10.000.000 dengan skor risiko 0,20 memberi penalti Rp300.000 dalam perbandingan rencana. Faktur tetap dihitung dari barang, ongkir, dan PPN.')

report.heading('Agent Dispatch dan Agent Angkut | Bobot jarak')
report.formula('d(R) = ∑<sub>e ∈ R</sub> d<sub>e</sub>')
report.p('Dijkstra memakai jarak d<sub>e</sub> sebagai bobot tiap ruas. Dispatch memeriksa muatan, rute, dan jadwal dari rencana terpilih. Angkut menjalankan penjemputan dan pengantaran. Keduanya memakai hasil perencanaan yang sama tanpa pelatihan terpisah.')
report.source('[K11] supplier_training.py:47-116, 156-216 dan supplier_data.py:50-95; [K12] supply_chain.py:87-230; [K7] room-jobs.js:17-21.')

# 19 - references/reproduce.
report.page('Rujukan dan cara reproduksi', 'Kode lokal menjadi acuan perilaku; dokumentasi resmi menjelaskan algoritmenya')
report.heading('Rujukan implementasi dalam folder electronics/')
for text in [
    '<b>[K1] agent.py:</b> inferensi 122-136; pengatur fase mulai 226; API mulai 625.',
    '<b>[K2] domain.py:</b> daftar agen/fitur 14-29; katalog 59-68; label 72-85.',
    '<b>[K3] finance.py:</b> PPN simulasi, pencatatan, kas bebas dan setoran 14-86.',
    '<b>[K4] train.py:</b> sembilan kandidat 26-38; generator 41-65; split/pemilihan/artefak 70-113.',
    '<b>[K5]-[K8] web/:</b> app.js:20-27 (lantai); interiors.js:1-90,234-244 (tugas dan model); room-jobs.js:1-119 (aktivitas); district-3d.mjs:105-147 (truk dan karakter).',
    '<b>[K9] data/metrics.json:</b> model utama/cadangan dan metrik tersimpan, model_version 2.',
    '<b>[K10] data/models.joblib:</b> koefisien model Stock dan parameter SVM yang dipakai simulator.',
    '<b>[K11] supplier_training.py, supplier_data.py, data/supplier/metrics.json:</b> pembagian, model pengiriman, dan evaluasi.',
    '<b>[K12] supply_chain.py:</b> jarak berbobot, penawaran rute, dan alokasi pesanan.',
]:
    report.p(text, 'small', after=5)
report.heading('Dataset dan dokumentasi resmi algoritme')
refs = [
    ('D1', 'Company Purchasing Dataset - atribusi sumber dalam README proyek', 'https://www.kaggle.com/datasets/shahriarkabir/company-purchasing-dataset'),
    ('D2', 'Supply Chain Shipment Pricing Data - riwayat pengiriman SCMS', 'https://www.kaggle.com/datasets/divyeshardeshana/supply-chain-shipment-pricing-data'),
    ('A1', 'scikit-learn: Decision Trees', 'https://scikit-learn.org/stable/modules/tree.html#classification'),
    ('A2', 'scikit-learn: Ensembles (Random Forest, Extra Trees, Gradient Boosting)', 'https://scikit-learn.org/stable/modules/ensemble.html'),
    ('A3', 'scikit-learn: Logistic Regression', 'https://scikit-learn.org/stable/modules/linear_model.html#logistic-regression'),
    ('A4', 'scikit-learn: Support Vector Machines', 'https://scikit-learn.org/stable/modules/svm.html#classification'),
    ('A5', 'scikit-learn: Nearest Neighbors Classification', 'https://scikit-learn.org/stable/modules/neighbors.html#nearest-neighbors-classification'),
    ('A6', 'CatBoost: How training is performed', 'https://catboost.ai/docs/en/concepts/algorithm-main-stages'),
    ('A7', 'XGBoost: Introduction to Boosted Trees', 'https://xgboost.readthedocs.io/en/stable/tutorials/model.html'),
]
for code, title, url in refs:
    report.p(f'<b>[{code}]</b> <link href="{escape(url)}" color="#086FAD">{escape(title)}</link>', 'small', after=5)
report.heading('Perintah dari folder utama repositori')
report.p('Instalasi dan penyiapan model: <font face="Calibri-Bold">py -3.14 electronics/install.py</font><br/>Training ulang agen: <font face="Calibri-Bold">.\\electronics\\.venv\\Scripts\\python.exe electronics/train.py</font><br/>Training ulang model pengiriman: <font face="Calibri-Bold">.\\electronics\\.venv\\Scripts\\python.exe electronics/supplier_training.py</font><br/>Jalankan aplikasi: <font face="Calibri-Bold">.\\electronics\\.venv\\Scripts\\python.exe electronics/agent.py</font>', 'small')
report.p('Model dan dataset yang ada tidak diubah untuk membuat dokumen ini. Rentang tanggal dan jumlah baris dihitung dari CSV lokal; skor diekstrak dari metrics.json. Dokumentasi algoritme resmi ditinjau untuk penjelasan konsep.', 'small')
digest = hashlib.sha256((ROOT / 'electronics/data/spend_analysis_dataset.csv').read_bytes()).hexdigest()
report.p('Identitas dataset (SHA-256):<br/>' + digest, 'tiny')

assert report.number == report.count, (report.number, report.count)
report.c.save()
print(PDF)
print(f'{report.number} pages written')
