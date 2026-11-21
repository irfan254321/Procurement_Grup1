"""Public profile copy for the logistics companies represented in BIZ District."""

CARRIER_PROFILES = {
    "jne": {
        "description": "Profil JNE dalam simulasi BIZ District. Lihat alur penjemputan, kapasitas, aturan, dan estimasi biaya logistik.",
        "font_query": "family=Manrope:wght@400;500;600;700;800&family=Space+Grotesk:wght@400;500;600;700&display=swap",
        "body": """<section class="jne-hero profile-shell" aria-labelledby="jne-title">
  <div class="jne-intro">
    <p class="profile-kicker">JNE di BIZ District</p>
    <h1 id="jne-title">Jemput.<br><em>Antar.</em></h1>
    <p class="carrier-lead">Pengambilan dari vendor hingga serah terima di Gudang BIZ.</p>
    <a class="profile-button" href="#layanan">Ikuti alur kiriman</a>
  </div>
  <figure class="jne-photo">
    <img src="/assets/profile-jne.webp" width="1440" height="960" fetchpriority="high" alt="Ilustrasi paket yang disiapkan di area muat gudang">
    <figcaption>Penjemputan dan pengantaran darat dalam simulasi</figcaption>
  </figure>
</section>
<section class="jne-service profile-shell" id="layanan" aria-labelledby="jne-service-title">
  <div class="jne-service-intro" data-profile-reveal>
    <p class="profile-kicker">Operasi di distrik</p>
    <h2 id="jne-service-title">Dari vendor ke Gudang BIZ.</h2>
    <p>Profil ini mengambil konteks layanan kargo JTR JNE. Di distrik, pengiriman mengikuti rute darat yang dipilih dari penawaran pemasok.</p>
    <dl class="jne-capacity">
      <dt>Batas muatan simulasi</dt>
      <dd><strong>8</strong> unit per kiriman</dd>
    </dl>
  </div>
  <div class="jne-dispatch" data-profile-reveal>
    <dl class="jne-stages">
      <div><dt>Terminal</dt><dd>Agent Dispatch memeriksa rute, jadwal, dan jumlah muatan.</dd></div>
      <div><dt>Vendor</dt><dd>Agent Angkut menjemput barang yang telah disiapkan.</dd></div>
      <div><dt>Gudang BIZ</dt><dd>Barang diserahkan untuk pemeriksaan dan pencatatan penerimaan.</dd></div>
    </dl>
    <div class="carrier-actions">
      <a class="profile-button" href="#biaya-logistik">Hitung ongkir JNE</a>
      <a class="carrier-text-link" href="#aturan">Aturan pengiriman</a>
    </div>
  </div>
</section>""",
    },
    "jt-cargo": {
        "description": "Profil J&T Cargo dalam simulasi BIZ District. Bandingkan layanan reguler dan ekspres, kapasitas, dan perkiraan ongkir.",
        "font_query": "family=Barlow+Condensed:wght@600;700;800&family=Public+Sans:wght@400;500;600;700;800&display=swap",
        "body": """<section class="jtc-hero profile-shell" aria-labelledby="jtc-title">
  <div class="jtc-poster">
    <p class="profile-kicker">J&amp;T Cargo di BIZ District</p>
    <h1 id="jtc-title">Muatan besar.<br><em>Rute darat.</em></h1>
    <div class="jtc-poster-end">
      <p class="carrier-lead">Atur pengiriman kargo sesuai muatan, jarak, dan tenggat.</p>
      <a class="profile-button" href="#layanan">Bandingkan layanan</a>
    </div>
  </div>
  <div class="jtc-visual">
    <img src="/assets/profile-jt-cargo.webp" width="1440" height="960" fetchpriority="high" alt="Ilustrasi truk yang digunakan untuk angkutan kargo darat">
    <dl class="jtc-capacity">
      <dt>Batas muatan simulasi</dt>
      <dd><strong>12</strong> unit per kiriman</dd>
    </dl>
  </div>
</section>
<section class="jtc-services profile-shell" id="layanan" aria-labelledby="jtc-services-title">
  <div class="jtc-service-heading" data-profile-reveal>
    <p class="profile-kicker">Layanan simulasi</p>
    <h2 id="jtc-services-title">Pilih sesuai pesanan.</h2>
    <p>J&amp;T Cargo melayani kargo melalui jalur darat. Opsi pengiriman dalam BIZ District dibedakan menurut waktu tempuh, rute, dan tarif model simulasi.</p>
  </div>
  <div class="jtc-options" data-profile-reveal>
    <article><h3>Reguler</h3><p>Simulasi membandingkan jalur melalui Hub Utara dan Hub Selatan untuk mencari rute yang tersedia.</p></article>
    <article><h3>Ekspres</h3><p>Rute melalui Hub Selatan memakai faktor waktu tempuh dan tarif yang berbeda.</p></article>
  </div>
  <div class="carrier-actions">
    <a class="profile-button" href="#biaya-logistik">Hitung ongkir J&amp;T Cargo</a>
    <a class="carrier-text-link" href="#aturan">Aturan pengiriman</a>
  </div>
</section>""",
    },
    "pos-logistik": {
        "description": "Profil Pos Logistik Indonesia dalam simulasi BIZ District. Lihat peran operasional, kapasitas, aturan, dan estimasi ongkir.",
        "font_query": "family=DM+Sans:wght@400;500;600;700&family=Playfair+Display:ital,wght@0,500;0,600;1,500&display=swap",
        "body": """<section class="pos-hero" aria-labelledby="pos-title">
  <img class="pos-backdrop" src="/assets/profile-pos-logistik.webp" width="1440" height="960" fetchpriority="high" alt="Ilustrasi rak palet dan area penyimpanan di fasilitas logistik">
  <div class="pos-hero-inner profile-shell">
    <p class="profile-kicker">Pos Logistik Indonesia di BIZ District</p>
    <h1 id="pos-title">Ruang untuk<br><em>lebih banyak.</em></h1>
    <p class="carrier-lead">Pengelolaan muatan dari terminal, pemasok, hingga gudang tujuan.</p>
    <a class="profile-button" href="#layanan">Lihat operasi logistik</a>
  </div>
</section>
<section class="pos-services profile-shell" id="layanan" aria-labelledby="pos-services-title">
  <div class="pos-capacity" data-profile-reveal>
    <dl>
      <dt>Batas muatan simulasi</dt>
      <dd><strong>16</strong><span>unit per kiriman</span></dd>
    </dl>
    <p>Kapasitas ikut menentukan jumlah yang dapat dialokasikan Pengadaan ke satu pengiriman.</p>
  </div>
  <div class="pos-service-copy" data-profile-reveal>
    <p class="profile-kicker">Transportasi dan pergudangan</p>
    <h2 id="pos-services-title">Dari terminal sampai serah terima.</h2>
    <p>Pos Logistik Indonesia bergerak di bidang transportasi, pergudangan, dan kargo. Dalam BIZ District, tim terminal memeriksa rencana pengiriman sebelum pengangkut mengambil muatan di vendor dan menyerahkannya ke Gudang BIZ.</p>
    <p>Dashboard menampilkan estimasi menurut pemasok, jarak, jenis layanan, dan jumlah barang.</p>
    <div class="carrier-actions">
      <a class="profile-button" href="#biaya-logistik">Hitung ongkir Pos Logistik</a>
      <a class="carrier-text-link" href="#aturan">Aturan pengiriman</a>
    </div>
  </div>
</section>""",
    },
}
