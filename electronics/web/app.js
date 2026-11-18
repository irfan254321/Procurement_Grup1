const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const amount = n => new Intl.NumberFormat('id-ID',{maximumFractionDigits:2}).format(n);
const rupiah = n => 'Rp'+new Intl.NumberFormat('id-ID',{maximumFractionDigits:0}).format(n*10000);
const moneyFeatures = new Set(['harga pengadaan','kas bebas','dana tersedia','potensi penjualan','harga jual','kesediaan bayar',
  'penawaran','harga acuan','tawaran pembeli','harga minimum','tawaran penjual','batas pembeli']);
const percent = n => (100*n).toFixed(2).replace('.',',')+'%';
const openingLabels = {
  healthy:'stok banyak dan kas sehat',
  stock:'stok kosong',
  cash:'stok kosong dan dana terbatas',
  damage:'risiko kerusakan pada kiriman pertama',
  supply:'permintaan naik dan kapasitas vendor utama turun',
  normal:'hari penjualan biasa',
};
const autoUnavailable = 'Server yang berjalan belum mendukung mode otomatis. Hentikan server lama dengan Ctrl+C, lalu jalankan kembali server dari folder proyek ini.';
function activeMode(state){
  const mode=state?.mode;
  return Object.hasOwn(openingLabels,mode)?mode:'auto';
}
const offices = {
 buyer:{name:'Pelanggan',color:'#dfb955',icon:'★',level:0,x:3,y:3},
 seller:{name:'Toko elektronik',color:'#5ba591',icon:'▣',level:1,x:3,y:3},
 stock:{name:'Gudang',color:'#749cd4',icon:'▤',level:2,x:3,y:3},
 finance:{name:'Keuangan',color:'#b79bd3',icon:'$',level:3,x:3,y:3},
 procurement:{name:'Pengadaan',color:'#efad6f',icon:'≡',level:4,x:3,y:3},
 deal:{name:'Negosiasi',color:'#d28491',icon:'⇄',level:5,x:3,y:3},
};
const vendorLots=[[8.2,.8,2],[12.2,.8,3],[16.2,.8,2],[9.8,6.6,2],[15.0,6.6,3]];
const colors=['#76aa86','#5b8cb3','#c4936a','#8c86b8','#6c9da5'];
const vendors={};
const canvas = $('scene'), ctx = canvas.getContext('2d');
let world, models, selected='stock', timer, busy=false, playing=true;
let movement=0, paintedTick=-1, district3D;
let districtZoom=1;
function activateDistrict(){
  if(!window.WebGL2RenderingContext)return;
  import('/district-3d.mjs').then(async({createDistrict})=>{
    district3D=await createDistrict(canvas,offices,vendors,$('markers'));
    district3D.update(world);
    $('map-view-controls').hidden=false;
  }).catch(error=>console.warn('Peta 2D digunakan.',error));
}
const project=(x,y,z=0)=>[600+(x-y)*55,380+(x+y-5)*20-z];
function poly(points,color,stroke){
  ctx.beginPath();
  points.forEach(([x,y],i)=>i?ctx.lineTo(x,y):ctx.moveTo(x,y));
  ctx.closePath();ctx.fillStyle=color;ctx.fill();
  if(stroke){ctx.strokeStyle=stroke;ctx.stroke()}
}
function tile(x,y,w,d,z,color,stroke){
  poly([project(x,y,z),project(x+w,y,z),project(x+w,y+d,z),project(x,y+d,z)],color,stroke);
}
function block(x,y,w,d,h,base,top,left,right){
  poly([project(x,y+d,base),project(x+w,y+d,base),project(x+w,y+d,base+h),project(x,y+d,base+h)],left);
  poly([project(x+w,y,base),project(x+w,y+d,base),project(x+w,y+d,base+h),project(x+w,y,base+h)],right);
  tile(x,y,w,d,base+h,top);
}
function tree(x,y){
  block(x,y,.13,.13,18,0,'#9c7250','#76583c','#654630');
  block(x-.2,y-.2,.52,.52,32,16,'#98c273','#659d5a','#518451');
}
function person(px,py,t,color){
  const bob=Math.sin(t/145)*1.8;
  ctx.fillStyle=color;ctx.fillRect(px-5,py-15+bob,10,12);
  ctx.fillStyle='#e6b390';ctx.beginPath();ctx.arc(px,py-20+bob,5.5,0,7);ctx.fill();
}
function vendorBuilding(o){
  for(let floor=0;floor<o.floors;floor++){
    block(o.x,o.y,1.6,1.55,29,floor*31,o.color,'#f2ead6','#b7c7c3');
    for(const offset of [.16,.67,1.15])block(o.x+offset,o.y+1.55,.27,.03,14,floor*31+8,'#9fe0e4','#81b6c6','#6697a0');
  }
  block(o.x-.07,o.y-.07,1.74,1.69,8,o.floors*31,o.color,o.color,'#446654');
}
function tower(t, latest){
  const {x,y}=offices.stock;
  block(x,y,2.8,3,382,0,'#466b6d','#305254','#244343');
  for(const [role,o] of Object.entries(offices)){
    const z=o.level*62, [px,py]=project(x,y+3,z), active=role===latest?.role;
    poly([[px,py],[px+154,py+56],[px+154,py-4],[px,py-60]],active?'#f6ffca':'#e2ecde','#294943');
    const [dx,dy]=project(x+2,y+3,z+7);
    ctx.fillStyle=o.color;ctx.fillRect(dx-7,dy-10,32,10);
    ctx.fillStyle='#385b64';ctx.fillRect(dx+6,dy-21,11,11);
    person(dx-14+(active?Math.sin(t/320)*6:0),dy-6,active?t:0,o.color);
    if(role==='buyer'||role==='seller'){
      const count=role==='buyer'?Math.min(4,world?.queue?.length??0):Number(world?.phase==='seller'&&!!world?.case?.id);
      for(let index=0;index<count;index++){
        person(px+15+index*17,py-9+index*7,t+index*220,colors[index%colors.length]);
      }
    }
    if(active)poly([[dx-14,dy-48],[dx-8,dy-40],[dx-14,dy-32],[dx-20,dy-40]],'#8ac84c','#376239');
  }
  const [sx,sy]=project(x+2.83,y+1.55,300);
  ctx.save();ctx.translate(sx,sy);ctx.rotate(-.4);ctx.textAlign='center';ctx.font='bold 24px Trebuchet MS';ctx.fillStyle='#e9fbd8';ctx.fillText('BIZ',0,0);ctx.restore();
}
function draw(t){
  if(district3D)return;
  if($('map').hidden){requestAnimationFrame(draw);return;}
  ctx.fillStyle='#e5f2d4';ctx.fillRect(0,0,2000,1000);
  const latest=world?.history[0];
  for(let x=0;x<22;x++)for(let y=0;y<10;y++){
    const street=y===4||x===7||x===12||x===17;
    tile(x,y,1,1,0,street?'#829e92':(x+y)%2?'#bbdca4':'#b1d49c','#ffffff17');
    if(y===4)tile(x+.17,y+.48,.55,.06,1,'#dce5cd');
  }
  const objects=[[9,()=>tower(t,latest)]];
  for(const o of Object.values(vendors))objects.push([o.x+o.y+1,()=>vendorBuilding(o)]);
  for(const [x,y] of [[1,1],[2,8],[6,1],[19,2.7],[20.5,6.5],[8,9],[13.1,9.2]])objects.push([x+y,()=>tree(x,y)]);
  if(latest?.shipment==='shipping'&&vendors[latest.vendor]){
    const start=vendors[latest.vendor],f=Math.min(1,Math.max(0,(t-movement)/3400));
    const x=start.x+(5.1-start.x)*f,y=start.y+(3.55-start.y)*f;
    objects.push([x+y,()=>{block(x,y,.7,.36,18,0,'#fff3bd','#ebd687','#b7823c');block(x-.26,y,.26,.36,12,0,'#6fadd4','#568dad','#426d97')}]);
  }
  objects.sort((a,b)=>a[0]-b[0]).forEach(([,paint])=>paint());
  requestAnimationFrame(draw);
}
requestAnimationFrame(draw);

async function api(path,method='GET',payload){
  const options={method};
  if(payload!==undefined){
    options.headers={'Content-Type':'application/json'};
    options.body=JSON.stringify(payload);
  }
  const response=await fetch(path,options);
  if(response.status===404&&path==='/api/reset/auto')throw new Error(autoUnavailable);
  const result=await response.json();
  if(!response.ok)throw new Error(result.error||'Simulasi gagal dimuat. Coba lagi.');
  return result;
}
function line(name,value){return '<div class="line"><span>'+esc(name)+'</span><strong>'+esc(value)+'</strong></div>'}
function supplierFacts(supplier){
  if(!supplier)return '';
  return '<div class="supplier-stock">'+Object.entries(supplier.stock??{}).map(([product,quantity])=>
    '<span>'+esc(product)+' · '+esc(amount(quantity))+' unit</span>').join('')+'</div>'+
    line('Kapasitas tersedia',amount(supplier.capacity_remaining??supplier.capacity??0)+' unit')+
    line('Estimasi kirim simulasi',supplier.lead_days==null?'Belum dikutip':amount(supplier.lead_days)+' hari')+
    line('Skor risiko model',supplier.late_probability==null?'Belum dikutip':percent(supplier.late_probability));
}
function renderSuppliers(){
  const suppliers=Object.entries(world.suppliers??{});
  $('supplier-section').hidden=suppliers.length===0;
  if(!suppliers.length)return;
  $('supplier-day').textContent='Hari simulasi '+amount(world.day??0);
  $('supplier-context').textContent='Stok dan kapasitas mengikuti kondisi simulasi. Jadwal dan skor risiko memakai acuan pengiriman komoditas kesehatan. Skor belum dikalibrasi atau divalidasi untuk pengiriman elektronik.';
  $('supplier-list').innerHTML=suppliers.map(([name,supplier])=>'<article class="supplier-item"><h3><button data-supplier="'+esc(name)+'">'+esc(name)+'</button></h3>'+
    supplierFacts(supplier)+(supplier.source_vendor?'<p class="supplier-source">Acuan pemasok · '+esc(supplier.source_vendor)+'</p>':'')+'</article>').join('');
  const current=world.case?.orders;
  const orders=current?.length?current:world.last_purchase?.orders??[];
  const statusLabels={reserved:'Dana dicadangkan',packing:'Dikemas',shipping:'Dikirim',inspected:'Sudah diperiksa',invoice_hold:'Faktur ditahan',corrected:'Faktur dikoreksi',paid:'Dibayar'};
  $('supply-orders').innerHTML=orders.length?'<h3>Pembagian pesanan dan kiriman</h3><div class="supply-order-list">'+orders.map(order=>
    '<article class="supply-order"><strong>'+esc(order.vendor)+' · '+esc(amount(order.quantity))+' unit</strong><small>'+esc([order.id,statusLabels[order.status]??'Direncanakan'].filter(Boolean).join(' · '))+'</small>'+
    line('Biaya barang',rupiah(order.goods_cost??order.cost??0))+line('Ongkir',rupiah(order.freight??0))+line('Total faktur',rupiah(order.invoice??0))+
    (order.route?line('Layanan',order.route.name)+line('Rute',(order.route.path??[]).slice(1).join(' → ')):'')+
    (order.arrival_day==null?'':line('Perkiraan tiba','Hari '+amount(order.arrival_day)))+
    (order.deadline_day==null?'':line('Tenggat','Hari '+amount(order.deadline_day)))+
    (order.received_quantity==null?'':line('Layak jual / rusak',amount(order.received_quantity)+' / '+amount(order.damaged_quantity??0)+' unit'))+'</article>').join('')+'</div>':'';
}
$('supplier-list').onclick=event=>{
  const button=event.target.closest('[data-supplier]');
  if(!button||!vendors[button.dataset.supplier])return;
  followActivity=false;selected=button.dataset.supplier;render();openInterior(selected);
};
function render(next){
  if(next)world=next;
  if(!world||!models)return;
  district3D?.update(world);
  const mode=activeMode(world);
  const opening=openingLabels[world.opening]??openingLabels[mode];
  $('scenario-current').textContent=[mode==='auto'?'Sesi otomatis':'Sesi uji',opening&&'Awal '+opening].filter(Boolean).join(' · ');
  const latest=world.history[0], active=latest?.meeting?.vendor||latest?.vendor||latest?.inspection?.vendor;
  if(paintedTick!==world.tick){
    paintedTick=world.tick;movement=performance.now();
    const panel=$('live-scene');
    panel.hidden=!(latest?.meeting||latest?.shipment||latest?.inspection);
    if(latest?.inspection&&latest.shipment==='delivered'){
      panel.innerHTML=shippingScene(latest.shipment,latest.inspection.vendor,latest);
    }
    else if(latest?.inspection)panel.innerHTML=inspectionScene(latest);
    else if(latest?.meeting)panel.innerHTML=negotiationScene({company:'PT. Biz Indonesia Market',...latest.meeting});
    else if(latest?.shipment)panel.innerHTML=shippingScene(latest.shipment,
      latest.shipments?.length>1?`${latest.shipments.length} kiriman pemasok`:latest.vendor);
    else panel.replaceChildren();
  }
  $('clock').textContent='Giliran '+world.tick;
  const empty=world.products.some(p=>!p.units);
  for(const button of $('markers').children){
    const key=button.dataset.role,o=offices[key]||vendors[key];
    button.classList.toggle('selected',key===selected);
    button.classList.toggle('current',key===world.scene||key===active||latest?.shipments?.some(order=>order.vendor===key));
    button.classList.toggle('empty',key==='seller'&&empty);
    const label=(o.level!==undefined?'L'+(o.level+1)+' · ':'')+o.name+(key==='seller'&&empty?' · STOK KOSONG':'');
    const shortLabel=o.level!==undefined?'L'+(o.level+1):'V'+(o.index+1);
    button.innerHTML='<span class="marker-full">'+esc(label)+'</span><span class="marker-short" aria-hidden="true">'+esc(shortLabel)+'</span>';
    button.setAttribute('aria-label',label);
    button.title=label;
    button.setAttribute('aria-pressed',key===selected);
  }
  const vendor=vendors[selected],role=vendor?'vendor':selected,o=vendor||offices[selected];
  const agent=models.roles[role], event=world.history.find(e=>vendor?
    (e.meeting?.vendor===selected||e.vendor===selected||e.inspection?.vendor===selected||e.shipments?.some(order=>order.vendor===selected)):e.role===role);
  const agentModel=models.benchmark.agents[role];
  $('inspector').innerHTML='<h2>'+esc(o.name)+'</h2><p>'+esc(vendor?o.floors+' lantai · pemasok elektronik':agent[1])+'</p>'+
    '<div class="decision">'+(event?'<strong>'+esc(event.title)+'</strong><p>'+esc(event.detail)+'</p>':'<p>Menunggu giliran agen.</p>')+'</div>'+
    '<small>Model utama · '+esc(agentModel.main)+'</small>'+
    (event?.prediction?'<p>Prediksi: '+esc(event.prediction)+'</p><details><summary>Masukan model</summary>'+
      Object.entries(event.features).map(([n,v])=>line(n,moneyFeatures.has(n)?rupiah(v):amount(v))).join('')+'</details>':'');
  if(vendor&&world.suppliers?.[selected])$('inspector').innerHTML+='<div class="decision"><strong>Kondisi pemasok</strong>'+supplierFacts(world.suppliers[selected])+'</div>';
  if(world.case?.offers?.length)$('inspector').innerHTML+='<details><summary>Hasil penawaran ('+world.case.offers.length+' / '+Object.keys(vendors).length+')</summary>'+
    world.case.offers.map(o=>line(o.vendor,o.accepted?rupiah(o.price)+' / unit':'Gagal sepakat')).join('')+'</details>';
  $('shelves').innerHTML=world.products.map(p=>line(p.name,(p.units?p.units+' unit':'STOK KOSONG')+' · '+customerPriceLabel(p.retail))).join('');
  const holds=Object.entries(world.restock_holds??{});
  $('restock-holds').hidden=holds.length===0;
  $('restock-hold-lines').innerHTML=holds.map(([product,hold])=>'<div class="decision">'+
    line(product,amount(hold.quantity)+' unit')+
    line('Dana tersedia',rupiah(hold.available))+
    line('Minimum pembelian',rupiah(hold.required))+
    line('Kekurangan dana',rupiah(hold.shortfall))+'</div>').join('');
  const pending=roomOrders(world).map(order=>[order,order.status]);
  const orderLine=(c,status)=>line('Pelanggan '+c.id,c.quantity+' × '+c.product+' · '+status);
  const recent=(world.customer_results??[]).filter(c=>c.status!=='Menunggu stok'&&!pending.some(([order])=>order.id===c.id)).slice(0,5);
  $('customers').innerHTML=(pending.length?'<div class="customer-list">'+pending.map(([c,status])=>orderLine(c,status)).join('')+'</div>':'<p>Antrean kosong.</p>')+
    (recent.length?'<details><summary>Hasil terakhir</summary>'+recent.map(c=>line('Pelanggan '+c.id,c.product+' · '+c.status)).join('')+'</details>':'');
  const purchase=world.last_purchase,sale=world.last_sale;
  function transaction(title, data, entries){
    if(!data)return '<p>'+esc(title)+' belum ada.</p>';
    return '<div class="decision"><strong>'+esc(title+' · '+data.product)+'</strong>'+
      (data.vendor?'<p>'+esc(data.vendor+' · '+data.status)+'</p>':data.customer?'<p>Pelanggan '+esc(data.customer)+'</p>':'')+
      entries.map(([key,value,units])=>line(key,units?amount(value)+' unit':rupiah(value))).join('')+'</div>';
  }
  $('transactions').innerHTML=transaction('Pengadaan terakhir',purchase,purchase?[
    ['Jumlah dipesan',purchase.quantity,true],
    ...(purchase.received_quantity==null?[]:[['Layak jual',purchase.received_quantity,true],['Rusak',purchase.damaged_quantity,true]]),
    ['Harga beli / unit',purchase.unit_cost],['Biaya barang dan ongkir',purchase.cost],
    ...(purchase.freight==null?[]:[['Ongkir pengadaan',purchase.freight]]),
    ...(purchase.vat==null?[]:[['PPN faktur',purchase.vat]]),
    ...(purchase.invoice_original!=null&&purchase.invoice_original!==purchase.invoice?
      [['Faktur awal',purchase.invoice_original],['Faktur setelah koreksi',purchase.invoice]]:
      purchase.invoice==null?[]:[['Total faktur vendor',purchase.invoice]]),
    ['Harga jual dasar / unit',purchase.retail],['Kas bebas saat keputusan',purchase.free_cash],['Anggaran saat keputusan',purchase.fund],
    ['Omzet jika semua terjual',purchase.revenue],['Laba kotor / unit',purchase.profit_per_unit],
    ['Proyeksi laba kotor',purchase.profit]]:[])+transaction('Penjualan terakhir',sale,sale?[
    ['Unit terjual',sale.quantity,true],['Harga jual dasar / unit',sale.retail],['Pendapatan sebelum PPN',sale.revenue],...(sale.vat==null?[]:[['PPN keluaran',sale.vat],['Total dibayar pelanggan',sale.total]]),
    ['Harga pokok penjualan',sale.cost],['Laba kotor aktual',sale.profit]]:[]);
  $('ledger').innerHTML=[['Saldo kas',world.cash],['Dana gaji',world.payroll],['Dana dicadangkan untuk PO',world.reserved??0],
    ['Operasional',world.operations],['Cadangan kas',world.reserve],['Sisa anggaran pengadaan',world.fund],
    ...(world.reinvested==null?[]:[['Laba dialokasikan ke restok',world.reinvested]]),
    ['Pendapatan penjualan',world.sales],['Laba kotor penjualan',world.sales-world.cogs]].map(([n,v])=>line(n,rupiah(v))).join('');
  renderInterior();
  renderSuppliers();
  renderFinance();
  $('history').innerHTML=world.history.map(e=>'<li><small>Giliran '+e.tick+'</small><div><strong>'+esc(e.title)+'</strong> · '+esc(models.roles[e.role][0])+'<p>'+esc(e.detail)+'</p></div></li>').join('')||'<li>Menunggu giliran pertama.</li>';
}
function benchmark(){
  $('benchmark').innerHTML=Object.entries(models.benchmark.agents).map(([role,data])=>{
    const rows=Object.entries(data.candidates).sort(([a,x],[b,y])=>{
      const rank=n=>data.selected.includes(n)?data.selected.indexOf(n):5;
      return rank(a)-rank(b)||y.validation-x.validation;
    });
    return '<section class="card"><h2>'+esc(models.roles[role][0])+'</h2><p>'+esc(models.roles[role][1])+'</p>'+
      '<p>Akurasi tebakan kelas mayoritas: '+percent(data.baseline)+'</p><table class="metrics"><thead><tr><th>Model</th><th>Validasi seimbang</th><th>Akurasi uji</th><th>Status</th></tr></thead><tbody>'+
      rows.map(([name,m])=>'<tr class="'+(name===data.main?'main':'')+'"><td>'+esc(name)+'</td><td>'+percent(m.validation)+'</td><td>'+percent(m.accuracy)+'</td><td>'+
        (name===data.main?'Utama':data.selected.includes(name)?'Cadangan':'—')+'</td></tr>').join('')+'</tbody></table></section>';
  }).join('');
  const supplier=models.supplier_model;
  const panel=$('supplier-benchmark');
  panel.hidden=!supplier?.late?.test||!supplier?.lead?.test;
  if(panel.hidden)return;
  const risk=supplier.late.test,lead=supplier.lead.test,parts=supplier.split?.partitions??[];
  const source=supplier.dataset??{};
  const url=/^https:\/\/www\.kaggle\.com\/datasets\//.test(source.kaggle_url??'')?source.kaggle_url:null;
  panel.innerHTML='<h2>Model pengiriman pemasok</h2><p>'+(url?'<a href="'+esc(url)+'" target="_blank" rel="noopener noreferrer">'+esc(source.title??'Dataset Kaggle pemasok')+'</a>':esc(source.title??'Riwayat pemasok'))+
    ' · '+esc(amount(supplier.cleaning?.source_rows??0))+' baris sumber. Riwayat pengiriman komoditas kesehatan digunakan sebagai acuan simulasi elektronik.</p>'+
    '<p class="supplier-partitions">'+parts.map(part=>esc(({train:'Latih',validation:'Validasi',test:'Uji'})[part.name]??part.name)+' '+esc(amount(part.rows))).join(' · ')+'</p>'+
    '<div class="supplier-evaluation"><div><h3>Risiko terlambat · CatBoost</h3><table class="metrics"><thead><tr><th>Ukuran uji</th><th>Model</th><th>Pembanding</th></tr></thead><tbody>'+
    '<tr><td>Balanced accuracy</td><td>'+percent(risk.balanced_accuracy)+'</td><td>'+percent(risk.baseline_balanced_accuracy)+'</td></tr>'+
    '<tr><td>Akurasi</td><td>'+percent(risk.accuracy)+'</td><td>'+percent(risk.baseline_always_on_time_accuracy)+'</td></tr>'+
    '<tr><td>Precision terlambat</td><td>'+percent(risk.precision)+'</td><td>—</td></tr>'+
    '<tr><td>Recall terlambat</td><td>'+percent(risk.recall)+'</td><td>—</td></tr></tbody></table><p>Pembanding selalu menebak tepat waktu. Kejadian terlambat jarang; periksa precision dan recall bersama akurasi.</p></div>'+
    '<div><h3>Waktu kirim · '+esc(supplier.lead.selected_model==='ScheduledBaseline'?'jadwal sebagai acuan':'CatBoost residual')+'</h3>'+line('MAE uji yang dipakai',amount(lead.mae_days)+' hari')+
    line('MAE model regresi',amount(lead.residual_model_mae_days)+' hari')+line('MAE jadwal acuan',amount(lead.baseline_scheduled_mae_days)+' hari')+
    '<p>MAE lebih kecil lebih baik. Metode waktu dipilih dari validasi. Waktu historis dibagi 30 dan dibatasi 1–12 hari untuk simulasi; akurasinya belum diuji pada elektronik.</p></div></div>';
}
function schedule(){clearTimeout(timer);if(playing&&models)timer=setTimeout(advance,Number($('pace').value))}
function pause(){playing=false;clearTimeout(timer);$('play').textContent='▶ Putar dunia'}
async function change(path,payload){
  if(busy||!models)return;
  busy=true;$('step').disabled=true;$('reset').disabled=true;$('error').textContent='';
  try{
    const next=await api(path,'POST',payload),e=next.history[0];
    if(followActivity)selected=e?.role==='vendor'?(e.meeting?.vendor||e.vendor||e.inspection?.vendor||'procurement'):next.scene;
    render(next);
    return true;
  }catch(e){
    if(payload!==undefined)throw e;
    pause();$('error').textContent=e.message;
  }
  finally{busy=false;$('step').disabled=false;$('reset').disabled=false}
}
async function advance(){await change('/api/step/'+activeMode(world));schedule()}
let followActivity=true;
function markers(){
 for(const [key,o] of Object.entries({...offices,...vendors})){
   const button=document.createElement('button');
   const position=o.level===undefined?project(o.x+.8,o.y+.8,o.floors*31+20):project(o.x+.68,o.y+3,o.level*62+31);
   button.className='office';button.dataset.role=key;button.style.left=position[0]/20+'%';button.style.top=position[1]/10+'%';
   button.textContent=o.name;button.onclick=()=>{followActivity=false;selected=key;render();openInterior(key)};
   $('markers').append(button);
 }
}
$('step').onclick=()=>{pause();advance()};
$('play').onclick=()=>{if(playing){pause();return}playing=true;followActivity=true;$('play').textContent='⏸ Jeda';advance()};
$('pace').onchange=schedule;
function zoomDistrict(value){
  if(!district3D)return;
  districtZoom=district3D.setZoom(value);
  $('map-zoom-value').textContent=Math.round(districtZoom*100)+'%';
}
$('map-zoom-in').onclick=()=>zoomDistrict(districtZoom+.15);
$('map-zoom-out').onclick=()=>zoomDistrict(districtZoom-.15);
$('map-zoom-reset').onclick=()=>zoomDistrict(1);
$('reset').onclick=async()=>{
  if(!models)return;
  const scenario=$('scenario').value;
  if(scenario==='auto'&&Array.isArray(models.scenarios)&&!models.scenarios.includes(scenario)){
    pause();
    $('error').textContent=autoUnavailable;
    return;
  }
  if(!confirm('Mulai ulang stok, kas, dan riwayat simulasi?'))return;
  pause();followActivity=true;
  if(await change('/api/reset/'+scenario)){playing=true;$('play').textContent='⏸ Jeda';schedule()}
};
document.querySelectorAll('.tab').forEach(button=>button.onclick=()=>{
 document.querySelectorAll('.tab').forEach(b=>{
   b.classList.toggle('active',b===button);
   b.setAttribute('aria-pressed',b===button);
 });
 window.scrollTo(0,0);
 for(const id of ['world','profit','models'])$(id).hidden=id!==button.dataset.tab;
 if(button.dataset.tab==='profit')renderFinance();
 if(button.dataset.tab==='world'){
   district3D?.update(world);
   sceneSignature='';
   renderInterior();
 }else{
   room3D?.stop();
 }
});
document.addEventListener('DOMContentLoaded',async()=>{
 try{
  if(typeof roomOrders!=='function'||typeof renderInterior!=='function'||typeof roomJobs!=='function'
      ||typeof negotiationScene!=='function'||typeof shippingScene!=='function'||typeof inspectionScene!=='function'){
    throw new Error('Berkas tampilan belum lengkap. Muat ulang halaman untuk melanjutkan.');
  }
  const [initial,metadata]=await Promise.all([api('/api/world'),api('/api/models')]);
  models=metadata;
  $('scenario').value=activeMode(initial);
  const names=[...new Set(initial.products.flatMap(p=>p.vendors.map(v=>v.name)))].sort();
  names.forEach((name,i)=>{const [x,y,floors]=vendorLots[i];vendors[name]={name,x,y,floors,index:i,color:colors[i]}});
  markers();render(initial);benchmark();activateDistrict();
  if(playing){$('play').textContent='⏸ Jeda';schedule()}
 }catch(error){
  pause();
  $('error').textContent=error.message;
 }
},{once:true});
