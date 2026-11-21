"""Editorial profile content for the five simulated electronics suppliers."""

SUPPLIER_PROFILES = {
    "cloudsoft": {
        "description": "Profil CloudSoft Corp. di BIZ District, pemasok elektronik dalam skenario pengadaan saat kapasitas terbatas.",
        "font_query": "family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&display=swap",
        "body": """
<div class="cloud-frame">
  <section class="cloud-bento profile-shell" aria-labelledby="profile-title">
    <div class="cloud-message">
      <p class="profile-kicker">CloudSoft Corp. · Pemasok elektronik</p>
      <h1 id="profile-title">Kapasitas<br>memberi <em>arah.</em></h1>
      <p>CloudSoft menawarkan laptop, monitor, dan printer kepada BIZ sesuai stok dan kapasitas yang tersedia.</p>
      <a class="profile-button" href="#ringkasan">Periksa stok dan kapasitas</a>
    </div>
    <div class="cloud-visual" aria-hidden="true">
      <div class="cloud-orbit cloud-orbit-outer"></div>
      <div class="cloud-orbit cloud-orbit-inner"></div>
      <div class="cloud-port cloud-port-one">Stok</div>
      <div class="cloud-port cloud-port-two">Kapasitas</div>
      <div class="cloud-port cloud-port-three">Tenggat</div>
      <div class="cloud-core"><strong>CS</strong></div>
    </div>
    <div class="cloud-figures">
      <div><strong>7 <small>unit</small></strong><span>Kapasitas per periode dalam kondisi normal</span></div>
      <div><strong>4 <small>unit</small></strong><span>Kapasitas pada skenario pasokan terbatas</span></div>
    </div>
  </section>
</div>
<section class="cloud-operations profile-shell supplier-section" id="operasi" aria-labelledby="cloud-ops-title" data-profile-reveal>
  <div>
    <p class="profile-kicker">Peran dalam simulasi</p>
    <h2 id="cloud-ops-title">Saat satu pemasok tak bisa memenuhi semua.</h2>
  </div>
  <div>
    <p>Dalam skenario pasokan terbatas, kebutuhan BIZ meningkat ketika kapasitas CloudSoft turun. CloudSoft dapat menawarkan sebagian dari jumlah yang diminta. Pengadaan BIZ membandingkan penawaran dari vendor lain untuk menutup kekurangannya.</p>
    <a href="#aturan">Baca aturan pasokan CloudSoft</a>
  </div>
</section>
""",
    },
    "furniworks": {
        "description": "Profil FurniWorks Ltd. di BIZ District, dengan alur pemenuhan pesanan dan penjemputan perangkat elektronik.",
        "font_query": "family=Bodoni+Moda:ital,wght@0,500;0,600;1,500&family=Manrope:wght@400;500;600;700&display=swap",
        "body": """
<section class="furni-collage profile-shell" aria-labelledby="profile-title">
  <figure class="furni-photo">
    <img src="/assets/profile-furniworks.webp" width="976" height="1220" alt="Ilustrasi ruang kerja untuk menyiapkan dan mengemas perangkat elektronik" fetchpriority="high">
  </figure>
  <div class="furni-copy">
    <p class="profile-kicker">FurniWorks Ltd. · Pemasok elektronik</p>
    <h1 id="profile-title">Dari katalog<br><em>ke ruang kerja.</em></h1>
    <p>FurniWorks menyiapkan perangkat elektronik untuk pesanan BIZ yang sudah disepakati.</p>
    <a class="profile-button" href="#ringkasan">Lihat katalog FurniWorks</a>
  </div>
  <p class="furni-categories">Laptop <span>·</span> Monitor <span>·</span> Printer</p>
</section>
<section class="furni-operations supplier-section" id="operasi" aria-labelledby="furni-ops-title">
  <div class="profile-shell furni-operations-inner" data-profile-reveal>
    <div>
      <p class="profile-kicker">Pemenuhan pesanan</p>
      <h2 id="furni-ops-title">Barang siap saat jadwal penjemputan tiba.</h2>
      <a href="#biaya-logistik">Lihat pilihan rute dan ongkir</a>
    </div>
    <dl>
      <div><dt>Periksa ketersediaan</dt><dd>Jumlah penawaran mengikuti stok per produk dan kapasitas periode berjalan.</dd></div>
      <div><dt>Siapkan pesanan</dt><dd>Setelah dana dicadangkan, unit yang disepakati dikemas untuk pengangkut terpilih.</dd></div>
      <div><dt>Catat penerimaan</dt><dd>Nilai barang pada faktur dapat dikoreksi jika gudang menemukan unit yang tidak layak jual.</dd></div>
    </dl>
  </div>
</section>
""",
    },
    "quickdeliver": {
        "description": "Profil QuickDeliver Ltd. di BIZ District, pemasok elektronik dengan alur penawaran, pengepakan, dan penjemputan.",
        "font_query": "family=Barlow+Condensed:wght@600;700;800&family=Space+Grotesk:wght@400;500;600;700&display=swap",
        "body": """
<section class="quick-hero profile-shell" aria-labelledby="profile-title">
  <div class="quick-copy">
    <p class="profile-kicker">QuickDeliver Ltd. · Pemasok elektronik</p>
    <h1 id="profile-title">Siap untuk<br>dijemput.</h1>
    <p>QuickDeliver memasok perangkat elektronik dan menyiapkan barang untuk penjemputan pengangkut.</p>
    <a class="profile-button" href="#biaya-logistik">Bandingkan biaya pengiriman</a>
  </div>
  <div class="quick-label">
    <p class="profile-kicker">Tujuan kiriman</p>
    <strong>Gudang<br>BIZ</strong>
    <p>Laptop, monitor, printer</p>
    <div class="quick-barcode" aria-hidden="true"></div>
  </div>
</section>
<section class="quick-operations supplier-section profile-shell" id="operasi" aria-labelledby="quick-ops-title">
  <div class="quick-operations-head" data-profile-reveal>
    <h2 id="quick-ops-title">Dari tawaran ke penjemputan.</h2>
    <p>Gulir ke samping untuk mengikuti tahap pemenuhan.</p>
  </div>
  <ol class="quick-stages" tabindex="0" aria-label="Tahap pemenuhan yang dapat digulir">
    <li><span>01</span><h3>Terima permintaan</h3><p>QuickDeliver mengecek stok dan menyampaikan harga serta jumlah yang bisa dipenuhi.</p></li>
    <li><span>02</span><h3>Kemas pesanan</h3><p>Pesanan yang disetujui disiapkan setelah dana dicadangkan. Barang menunggu pengangkut terpilih.</p></li>
    <li><span>03</span><h3>Serahkan ke pengangkut</h3><p>Pengangkut mengambil barang dan mengantarnya ke Gudang BIZ melalui rute pada pesanan.</p></li>
  </ol>
</section>
""",
    },
    "techmart": {
        "description": "Profil TechMart Inc. di BIZ District, pemasok laptop, monitor, dan printer dengan katalog, aturan, dan estimasi biaya pengiriman.",
        "font_query": "family=Chakra+Petch:wght@500;600;700&family=DM+Sans:wght@400;500;600;700&family=Space+Mono:wght@400;700&display=swap",
        "body": """
<div class="tech-layout profile-shell">
  <section class="tech-sticky" aria-labelledby="profile-title">
    <p class="profile-kicker">TechMart Inc. · Pemasok elektronik</p>
    <h1 id="profile-title">Perangkat untuk kebutuhan <em>BIZ.</em></h1>
    <p>TechMart memasok laptop, monitor, dan printer. Ikuti perjalanan perangkat dari katalog pemasok ke stok toko BIZ.</p>
    <a class="profile-button" href="#ringkasan">Lihat katalog TechMart</a>
  </section>
  <div class="tech-story">
    <figure class="tech-screen">
      <div class="tech-screen-image">
        <img src="/assets/profile-techmart.webp" width="1440" height="960" alt="Ilustrasi lini laptop dan monitor pada meja demonstrasi elektronik" fetchpriority="high">
      </div>
      <figcaption>Ilustrasi katalog elektronik TechMart</figcaption>
    </figure>
    <section class="tech-operations supplier-section" id="operasi" aria-labelledby="tech-ops-title" data-profile-reveal>
      <p class="profile-kicker">Katalog dan pemenuhan</p>
      <h2 id="tech-ops-title">Stok dan tujuan setiap perangkat.</h2>
      <p>Dashboard menampilkan harga katalog dan stok yang masih tersedia. Kiriman yang disepakati mengurangi persediaan TechMart, lalu menambah stok BIZ setelah barang diperiksa.</p>
      <ul class="tech-categories" aria-label="Produk katalog"><li>Laptop</li><li>Monitor</li><li>Printer</li></ul>
      <a href="#biaya-logistik">Periksa ongkir untuk jumlah yang dipilih</a>
    </section>
  </div>
</div>
""",
    },
}
