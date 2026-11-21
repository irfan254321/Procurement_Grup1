const companyDashboard = { key: null, tab: 'room', estimate: null, markup: '' };
const companyOrderStatus = {
  reserved: 'Dana dicadangkan', packing: 'Dikemas', shipping: 'Dikirim',
  inspected: 'Diperiksa', invoice_hold: 'Faktur ditahan', corrected: 'Faktur dikoreksi', paid: 'Dibayar',
};
const bizCompanyName = 'PT. Biz Indonesia Market';

function resetCompanyDashboard(){
  companyDashboard.key=null;
  companyDashboard.tab='room';
  companyDashboard.estimate=null;
}

function companyProducts(name){
  return world.products.flatMap(product=>{
    if(!name)return [{name:product.name,stock:product.units,price:product.retail}];
    const quote=product.vendors.find(vendor=>vendor.name===name);
    return quote?[{name:product.name,stock:world.suppliers?.[name]?.stock?.[product.name],price:quote.price}]:[];
  });
}

function companyTable(caption, headers, rows){
  return '<div class="company-table-scroll" tabindex="0" role="region" aria-label="'+esc(caption)+'"><table class="company-table"><caption>'+esc(caption)+'</caption><thead><tr>'+
    headers.map(header=>'<th scope="col">'+esc(header)+'</th>').join('')+'</tr></thead><tbody>'+
    rows.map(({id,cells})=>'<tr'+(id?' data-company-order="'+esc(id)+'"':'')+'>'+cells.map((cell,index)=>
      '<td data-label="'+esc(headers[index])+'"><div>'+cell+'</div></td>').join('')+'</tr>').join('')+
    '</tbody></table></div>';
}

function companyFact(label,value){
  return '<div><dt>'+esc(label)+'</dt><dd>'+esc(value)+'</dd></div>';
}

function companyProfile(name){
  const carrier=models.company_policy?.carriers?.[name];
  if(carrier){
    return '<div class="company-overview"><article class="company-block"><h4>Profil perusahaan</h4><p>'+esc(carrier.description)+'</p>'+
      (/^https:\/\//.test(carrier.source_url)?'<p class="company-note"><a href="'+esc(carrier.source_url)+'" target="_blank" rel="noopener noreferrer">Sumber profil resmi</a></p>':'')+
      '</article><article class="company-block"><h4>Operasi di BIZ District</h4><dl class="company-list">'+
      companyFact('Peran','Penjemputan, transit, dan pengantaran')+
      companyFact('Kapasitas simulasi',amount(carrier.capacity)+' unit / kiriman')+
      companyFact('Tujuan','Gudang BIZ')+'</dl><p class="company-note">Kapasitas, tarif, dan waktu tempuh ditetapkan untuk simulasi.</p></article></div>';
  }
  const supplier=world.suppliers?.[name];
  const catalogue=companyProducts(name);
  const days=supplier?.lead_days;
  const details=name?[
    ['Peran','Pemasok elektronik untuk BIZ'],
    ['Kapasitas tersisa',supplier?`${amount(supplier.capacity_remaining)} dari ${amount(supplier.capacity)} unit`:'Belum tersedia'],
    ['Estimasi reguler',days==null?'Menunggu penawaran':`${amount(days)} hari simulasi`],
    ['Skor risiko reguler',supplier?.late_probability==null?'Menunggu penawaran':percent(supplier.late_probability)],
  ]:[
    ['Peran','Distributor dan penjual elektronik'],
    ['Lokasi','Kantor pusat BIZ District'],
    ['Bagian','6 lantai'],
    ['Pemasok terdaftar',amount(Object.keys(vendors).length)+' perusahaan'],
    ['Pengangkut terdaftar',amount(Object.keys(carriers).length)+' perusahaan'],
  ];
  return '<div class="company-overview"><article class="company-block"><h4>Profil perusahaan</h4><dl class="company-list">'+
    details.map(([label,value])=>companyFact(label,value)).join('')+'</dl>'+
    (supplier?.source_vendor?'<p class="company-note">Acuan logistik historis · '+esc(supplier.source_vendor)+'. Profil dan kapasitas perusahaan mengikuti skenario simulasi.</p>':'')+
    '</article><article class="company-block">'+companyTable('Katalog elektronik',['Produk','Stok tersedia',name?'Harga katalog/unit':'Harga jual/unit'],
    catalogue.map(item=>({cells:[esc(item.name),item.stock==null?'—':esc(amount(item.stock)+' unit'),
      item.price==null?'—':esc(name?rupiah(item.price):customerPriceLabel(item.price))]})))+'</article></div>';
}

function companyRules(name){
  const rules=models.company_policy??{};
  const term=(value,label)=>value==null?'':amount(value)+' '+label;
  const rounds=term(rules.negotiation_rounds,'putaran');
  const refill=term(rules.supplier_replenish_ticks,'giliran');
  const markup=rules.min_markup==null?'':amount(rules.min_markup*100)+'%';
  const threshold=term(rules.restock_threshold,'unit');
  const carrier=rules.carriers?.[name];
  const supplier=world.suppliers?.[name];
  const supplierCapacity=Number.isFinite(supplier?.capacity)&&Number.isFinite(supplier?.capacity_remaining)
    ?'Kapasitas '+amount(supplier.capacity)+' unit per periode, dengan '+amount(supplier.capacity_remaining)+' unit tersisa. ':'';
  const data=carrier?[
    ['Batas muatan','Kapasitas simulasi '+amount(carrier.capacity)+' unit per kiriman. Pengadaan hanya memilih layanan dengan kapasitas yang mencukupi.'],
    ['Rute dan jadwal','Truk berangkat dari terminal pengangkut, menjemput barang di pemasok, lalu menuju Gudang BIZ. Pengiriman dipilih agar jadwal tiba memenuhi tenggat.'],
    ['Biaya per kiriman','Jarak ke terminal dan gudang memengaruhi biaya tetap. Tarif pengangkut, layanan, dan jumlah unit juga memengaruhi ongkir pada faktur pemasok.'],
    ['Serah terima','Petugas gudang memeriksa kondisi barang dan mencatat unit yang layak jual. Status faktur mengikuti pemeriksaan tersebut.'],
  ]:name?[
    ['Stok dan kapasitas','Pesanan mengurangi stok produk dan kapasitas tersedia setelah disetujui. '+
      supplierCapacity+
      (refill?'Kapasitas dipulihkan setiap '+refill+'.':'Kapasitas dipulihkan secara berkala.')],
    ['Harga dan negosiasi',(rules.offer_opening_multiplier!=null&&rules.offer_floor_multiplier!=null
      ?'Harga pembuka '+amount(rules.offer_opening_multiplier*100)+'% dan harga minimum '+amount(rules.offer_floor_multiplier*100)+'% dari harga katalog. '
      :'Harga penawaran mengikuti harga acuan dan batas minimum pemasok. ')+(rounds?'Maksimal '+rounds+' tawar balik.':'')],
    ['Penerimaan pesanan','Pemasok bisa menawarkan sebagian kebutuhan. Tawaran harus memenuhi harga minimum dan kapasitas, dengan keputusan respons dari model Vendor.'],
    ['Pengiriman dan faktur','Pemasok mengemas barang setelah dana dicadangkan. Jika jumlah layak jual berbeda, pemasok mengoreksi nilai barang pada faktur. Ongkir tetap dibebankan.'],
  ]:[
    ['Persediaan dan restok',(threshold?'Titik pesan '+threshold+'. ':'')+'Kekurangan stok atau kebutuhan dari antrean dapat memicu restok.'],
    ['Pemilihan pemasok','Pengadaan bisa membagi pesanan. Kombinasi dipilih berdasarkan harga, ongkir, dan skor risiko, dalam batas kapasitas, anggaran, serta tenggat.'],
    ['Persetujuan keuangan','Faktur harus terjangkau oleh kas dan anggaran. '+(markup?'Target selisih harga jual minimal '+markup+' dari biaya termasuk ongkir.':'Target laba pengadaan juga diperiksa.')],
    ['Penerimaan dan pembayaran','Gudang mencatat unit layak jual. Keuangan membayar setiap faktur setelah cocok dengan barang yang diterima.'],
  ];
  return '<h4>'+(carrier?'Aturan pengiriman dalam simulasi':'Aturan perusahaan')+'</h4><ol class="company-rules">'+data.map(([title,detail])=>
    '<li class="company-rule"><h5>'+esc(title)+'</h5><p>'+esc(detail)+'</p></li>').join('')+'</ol>';
}

function companyOrders(name){
  // last_purchase also points to the newest settled batch until another order starts.
  const all=new Map();
  const filterCarrier=Object.hasOwn(carriers,name);
  for(const batch of [...(world.purchase_orders??[]),world.last_purchase]){
    for(const order of batch?.orders??[]){
      const company=filterCarrier?order.route?.carrier:order.vendor;
      if(!order.id||!companyOrderStatus[order.status]||(name&&company!==name))continue;
      all.set(order.id,{...order, product:order.product??batch.product});
    }
  }
  return [...all.values()].reverse();
}

function companyTariffs(name){
  const available=models.company_policy?.suppliers??{};
  const carrier=Object.hasOwn(carriers,name)?name:null;
  const vendor=Object.hasOwn(vendors,name)?name:null;
  const suppliers=Object.keys(available).filter(key=>(!vendor||key===vendor)&&companyProducts(key).length);
  if(!suppliers.length)return '';
  const estimate=companyDashboard.estimate??={vendor:suppliers[0],product:null,quantity:1};
  if(!suppliers.includes(estimate.vendor))estimate.vendor=suppliers[0];
  const products=companyProducts(estimate.vendor);
  const product=products.find(item=>item.name===estimate.product)??products[0];
  estimate.product=product.name;
  const option=(value,current)=>'<option value="'+esc(value)+'"'+(value===current?' selected':'')+'>'+esc(value)+'</option>';
  const rounded=value=>Math.round((value+Number.EPSILON)*10000)/10000;
  const services=(available[estimate.vendor].services??[]).filter(service=>!carrier||service.carrier===carrier);
  const rows=services.map(service=>{
    const fixed=rounded(product.price*service.fixed_rate);
    const perUnit=rounded(product.price*service.unit_rate);
    const unavailable=service.capacity!=null&&service.capacity<estimate.quantity;
    const label=[service.name,carrier?null:service.carrier].filter(Boolean).join(' · ');
    return {cells:[esc(label)+'<small>'+esc((service.path??[]).join(' → '))+'</small>',
      companyDistance(service.distance),esc(rupiah(fixed)),esc(rupiah(perUnit)),
      unavailable?'Maks. '+esc(amount(service.capacity))+' unit':esc(rupiah(rounded(fixed+estimate.quantity*perUnit)))]};
  });
  return '<article class="company-block"><h4>Estimasi ongkir</h4><div class="company-controls">'+
    (vendor?'':'<label>Pemasok <select id="company-estimate-vendor">'+suppliers.map(value=>option(value,estimate.vendor)).join('')+'</select></label>')+
    '<label>Produk <select id="company-estimate-product">'+products.map(item=>option(item.name,estimate.product)).join('')+'</select></label>'+
    '<label>Jumlah unit <input id="company-estimate-quantity" type="number" min="1" max="40" value="'+estimate.quantity+'"></label></div>'+
    companyTable('Tarif per kiriman',['Layanan dan rute','Jarak simulasi','Biaya tetap','Per unit','Estimasi ongkir'],rows)+
    '<p class="company-note">Biaya tetap mengikuti jarak pada peta simulasi dan tarif pengangkut. Estimasi menambahkan biaya per unit sesuai jumlah barang. Perhitungan memakai harga katalog '+esc(rupiah(product.price))+' per unit. Faktur memakai harga hasil negosiasi.</p></article>';
}

function companyDistance(value){
  return Number.isFinite(value)?esc(amount(value)+' satuan'):'—';
}

function companyLogistics(name){
  const orders=companyOrders(name);
  const paid=orders.filter(order=>order.status==='paid');
  const open=orders.filter(order=>order.status!=='paid');
  const freight=list=>list.reduce((total,order)=>total+(order.freight??0),0);
  const kpi=(label,value,id)=>'<div class="company-kpi"><span>'+esc(label)+'</span><strong'+(id?' id="'+id+'"':'')+'>'+esc(value)+'</strong></div>';
  const limit=10;
  const rows=orders.slice(0,limit).map(order=>({id:order.id,cells:[
    '<strong>'+esc(order.product??'Barang elektronik')+'</strong><small>'+esc(order.id+(vendors[name]?'':' · '+order.vendor))+'</small>',
    esc(amount(order.quantity)+' unit'),esc([order.route?.name,order.route?.carrier].filter(Boolean).join(' · ')||'—')+
      (order.arrival_day==null?'':'<small>Hari '+esc(order.arrival_day)+'</small>'),
    companyDistance(order.route?.distance),
    order.freight==null?'—':esc(rupiah(order.freight)),
    '<span class="company-chip" data-status="'+esc(order.status)+'">'+esc(companyOrderStatus[order.status])+'</span>',
  ]}));
  return '<h4>Biaya logistik</h4><div class="company-kpis">'+
    kpi('Ongkir pada faktur dibayar',rupiah(freight(paid)),'company-paid-freight')+
    kpi('Ongkir pada faktur terbuka',rupiah(freight(open)),'company-open-freight')+
    kpi('Kiriman tercatat',amount(orders.length))+'</div>'+
    '<p class="company-note">Ongkir sebelum PPN dari pesanan tercatat dalam sesi simulasi ini.</p>'+
    (orders.length?companyTable('Kiriman terbaru',['Pesanan','Jumlah','Layanan dan jadwal','Jarak simulasi','Ongkir','Status faktur'],rows):
      '<p class="company-empty">Belum ada kiriman tercatat untuk perusahaan ini. Estimasi ongkir tersedia di bawah jika tarif sudah dimuat.</p>')+
    companyTariffs(name);
}

function renderCompanyDashboard(name){
  const key=name??'headquarters';
  if(companyDashboard.key!==key){
    resetCompanyDashboard();
    companyDashboard.key=key;
  }
  const tab=companyDashboard.tab;
  $('company-initials').textContent=name?name.split(/\s+/)[0].slice(0,2).toUpperCase():'BIZ';
  $('company-type').textContent=carriers[name]?'Perusahaan logistik':name?'Pemasok elektronik':'Distributor elektronik';
  const heading=$('company-name');
  heading.textContent=name??bizCompanyName;
  if(heading.tagName==='A')heading.href=models.company_policy?.pages?.[heading.textContent]??'/';
  $('company-context').textContent='Hari simulasi '+amount(world.day??0);
  for(const button of $('company-nav')?.querySelectorAll('[data-company-tab]')??[]){
    const active=button.dataset.companyTab===tab;
    button.setAttribute('aria-pressed',String(active));
  }
  const insideRoom=tab==='room';
  $('company-room').hidden=!insideRoom;
  const panel=$('company-panel');
  if(panel)panel.hidden=insideRoom;
  if(insideRoom||!panel)return true;
  renderCompanyPanel(name,tab);
  return false;
}

function renderCompanyPanel(name,tab){
  const panel=$('company-panel');
  const markup=tab==='profile'?companyProfile(name):tab==='rules'?companyRules(name):companyLogistics(name);
  if(companyDashboard.markup!==markup){
    const activeId=document.activeElement?.id;
    const draft=activeId==='company-estimate-quantity'?document.activeElement.value:null;
    panel.innerHTML=markup;
    companyDashboard.markup=markup;
    if(activeId?.startsWith('company-estimate-')){
      const control=$(activeId);
      if(control&&draft!=null)control.value=draft;
      control?.focus({preventScroll:true});
    }
  }
}

function updateCompanyEstimate(event, render){
  const estimate=companyDashboard.estimate;
  if(!estimate)return;
  switch(event.target.id){
    case 'company-estimate-vendor': estimate.vendor=event.target.value;break;
    case 'company-estimate-product': estimate.product=event.target.value;break;
    case 'company-estimate-quantity': {
      estimate.quantity=Math.max(1,Math.min(40,Math.trunc(Number(event.target.value))||1));
      event.target.value=estimate.quantity;
      break;
    }
    default:return;
  }
  render();
}
