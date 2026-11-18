const roomRoleNames = {
  buyer: ['Agent Resepsionis', 'Agent Konsultasi Produk'],
  seller: ['Agent Penjual', 'Agent Penyiapan Barang', 'Agent Kasir'],
  stock: ['Agent Stock', 'Agent Penerimaan Gudang', 'Agent Penataan Gudang'],
  finance: ['Agent Keuangan', 'Agent Anggaran', 'Agent Pembayaran'],
  procurement: ['Agent Pengadaan', 'Agent Analisis Vendor', 'Agent Pembelian'],
  deal: ['Agent Negosiasi', 'Agent Pencatat Negosiasi'],
  vendor: ['Agent Vendor', 'Agent Pengiriman Vendor'],
  carrier: ['Agent Dispatch', 'Agent Angkut'],
};

const roomDuties = {
  vendor: [
    ['Periksa stok dan kapasitas sebelum memberi penawaran.', 'Negosiasikan harga satuan dan jumlah yang dapat dipenuhi.', 'Koreksi faktur jika jumlah barang layak jual berbeda dari pesanan.'],
    ['Ambil dan cocokkan barang dengan pesanan yang disetujui.', 'Kemas barang dan siapkan muatan di area penjemputan.', 'Serahkan muatan kepada pengangkut yang dipilih untuk kiriman tersebut.'],
  ],
  carrier: [
    ['Periksa jumlah muatan dan batas kapasitas kendaraan.', 'Cocokkan perusahaan pemasok, rute, dan jadwal tiba pada rencana kiriman.', 'Catat serah terima setelah barang tiba di gudang pemesan.'],
    ['Berangkat dari terminal menuju pemasok yang tertera di pesanan.', 'Berhenti untuk mengambil dan memuat barang.', 'Ikuti rute kiriman dan serahkan barang ke gudang pemesan.'],
  ],
};

const roomStandby = {
  buyer: ['Siap menyambut pelanggan', 'Siap menjelaskan pilihan produk'],
  seller: ['Siap menilai pesanan', 'Siap mengambil barang', 'Menunggu pembayaran'],
  stock: ['Siap mengecek persediaan', 'Menunggu kedatangan barang', 'Siap menata rak'],
  finance: ['Menunggu pemeriksaan kas', 'Siap mengecek anggaran', 'Menunggu invoice'],
  procurement: ['Menunggu permintaan restok', 'Menunggu tawaran vendor', 'Siap mencatat pesanan'],
  deal: ['Menunggu penawaran', 'Siap mencatat kesepakatan'],
  vendor: ['Menunggu permintaan penawaran', 'Menunggu pesanan untuk dikemas'],
  carrier: ['Menunggu rute kiriman', 'Menunggu jadwal penjemputan'],
};

function roomJobs(role, event, live) {
  const jobs = Object.fromEntries((roomStandby[role] ?? []).map((label, i) => [
    'staff-' + i, {label, kind: 'idle'},
  ]));
  if (!event || !live) return jobs;

  const assign = (i, label, kind, to) => {
    jobs['staff-' + i] = to ? {label, kind, to} : {label, kind};
  };
  switch (role) {
    case 'buyer':
      assign(0, 'Mencatat pelanggan yang datang', 'type');
      assign(1, 'Menyambut pelanggan di lobi', 'walk', [6.6, 4.2]);
      break;
    case 'seller':
      if (event.title === 'Penjualan berhasil') {
        assign(0, 'Mengonfirmasi pesanan', 'talk');
        assign(1, 'Membawa barang ke kasir', 'carry', [7.1, 5.3]);
        assign(2, 'Memindai barang dan mencetak struk', 'scan');
      } else if (/^(stok kosong|stok tidak cukup|pesanan tertunda)$/i.test(event.title)) {
        assign(0, 'Menutup transaksi karena stok kurang', 'talk');
        assign(1, 'Mengecek barang di rak toko', 'scan', [4.9, 2.6]);
      } else {
        assign(0, 'Meninjau permintaan pelanggan', 'type');
      }
      break;
    case 'stock':
      if (event.inspection?.state === 'inspected') {
        assign(0, 'Mencatat jumlah barang layak jual', 'type');
        assign(1, 'Memeriksa jumlah dan kondisi barang', 'scan', [9.2, 6.3]);
        if (event.inspection.accepted) assign(2, 'Menata unit yang lolos ke rak', 'carry', [5.4, 2.7]);
      } else if (event.shipment === 'delivered' || event.title === 'Barang diterima') {
        assign(0, 'Memperbarui jumlah stok', 'type');
        assign(1, 'Menerima dan memindai kardus', 'scan', [9.2, 6.3]);
        assign(2, 'Membawa kardus ke rak gudang', 'carry', [5.4, 2.7]);
      } else {
        assign(0, 'Mengecek jumlah persediaan', 'type');
        assign(2, 'Mencocokkan isi rak dengan catatan stok', 'walk', [5.4, 2.7]);
      }
      break;
    case 'finance':
      if (event.inspection?.state === 'invoice_hold') {
        assign(0, 'Memeriksa selisih jumlah barang dan faktur', 'type');
        assign(2, 'Menahan pembayaran dan meminta koreksi', 'mail');
      } else if (event.inspection?.state === 'paid') {
        assign(2, 'Mencocokkan hasil pemeriksaan dan membayar faktur', 'stamp');
      } else if (event.shipment === 'delivered') {
        assign(2, 'Mencatat invoice yang sudah dibayar', 'stamp');
      } else {
        assign(0, event.title === 'Pembelian disetujui'
          ? 'Menyetujui dana pengadaan' : 'Memeriksa kemampuan kas', 'stamp');
        assign(1, 'Mengecek pagu pengadaan', 'type');
      }
      break;
    case 'procurement':
      if (event.title === 'Permintaan penawaran') {
        assign(0, 'Mengirim permintaan harga ke vendor', 'mail');
        assign(2, 'Menyiapkan rincian jumlah barang', 'type');
      } else {
        assign(0, event.title === 'Vendor terpilih' ? 'Meneruskan pilihan ke Keuangan' : 'Mencatat hasil pengadaan',
          event.title === 'Vendor terpilih' ? 'mail' : 'type');
        assign(1, 'Membandingkan penawaran final', 'type');
      }
      break;
    case 'deal': {
      const speaker = event.meeting?.event?.speaker;
      assign(0, speaker === 'vendor' ? 'Menyimak jawaban vendor' : 'Menyampaikan keputusan penawaran',
        speaker === 'vendor' ? 'idle' : 'talk');
      assign(1, 'Mencatat nilai penawaran', 'type');
      if (event.meeting) jobs.visitor = speaker === 'vendor'
        ? {label: 'Menjawab penawaran', kind: 'talk'}
        : {label: 'Menyimak penawaran', kind: 'idle'};
      break;
    }
    case 'vendor':
      if (event.inspection?.state === 'invoice_corrected') {
        assign(0, 'Mengirim faktur yang sudah dikoreksi', 'mail');
      } else if (event.shipment === 'packing' || event.shipment === 'shipping') {
        assign(1, event.shipment === 'packing' ? 'Membawa kardus dari area pengemasan' : 'Membawa kardus ke area muat',
          'carry', event.shipment === 'packing' ? [5.5, 4.5] : [9.6, 6.7]);
      } else {
        assign(0, 'Menanggapi tawaran pembeli', 'talk');
      }
      break;
    case 'carrier':
      assign(0,event.inspection?'Mencatat serah terima':'Memeriksa rute dan muatan','type');
      if(event.shipment==='shipping')assign(1,'Menjemput dan mengantar barang','carry',[9.3,6.2]);
      if(event.inspection?.state==='inspected')assign(1,'Menyerahkan muatan ke gudang pemesan','carry',[9.3,6.2]);
      break;
  }
  return jobs;
}
