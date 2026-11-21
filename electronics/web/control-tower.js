const memoryRoles={buyer:'Pembeli',seller:'Penjual',stock:'Gudang',procurement:'Pengadaan',
  vendor:'Vendor',deal:'Negosiasi',finance:'Keuangan',orchestrator:'Orkestrator'};
let towerSnapshot, towerLoading=false, memoryRequest=0;
let inspectorKey, inspectorResult, inspectorRequest;

function towerCard(title, markup){
  return '<article class="card tower-card"><h2>'+esc(title)+'</h2>'+markup+'</article>';
}
function tableRows(title, headers, rows){
  return towerCard(title,rows.length?companyTable(title,headers,rows.map(cells=>({cells:cells.map(esc)}))):'<p>Belum ada data pada skenario ini.</p>');
}
function optionalValue(value, prefix=''){return value==null?'—':prefix+amount(value)}
function renderTower(){
  const snapshot=towerSnapshot;
  if(!snapshot)return;
  const selector=$('tower-cycle'),selected=selector.value;
  selector.innerHTML=snapshot.cycles.map(cycle=>'<option value="'+esc(cycle.cycle)+'">'+esc(cycle.cycle+' · '+(cycle.purchase_plan.product??'Pengadaan'))+'</option>').join('');
  if(snapshot.cycles.some(cycle=>cycle.cycle===selected))selector.value=selected;
  const cycle=snapshot.cycles.find(x=>x.cycle===selector.value)??snapshot.cycles[0];
  if(cycle){
    const plan=cycle.purchase_plan, end=cycle.projected_completion;
    $('tower-outputs').innerHTML=
      towerCard('Rencana pembelian', '<p>'+esc(plan.formula)+'</p>'+line('Jumlah dialokasikan',plan.allocated_units+' / '+plan.requested_units+' unit')+
        line('Biaya barang (C)',rupiah(plan.goods_cost))+line('Ongkir',rupiah(plan.freight))+
        line('PPN 11%',rupiah(plan.vat))+line('Total faktur PO',rupiah(plan.invoice)))+
      tableRows('Alokasi pemasok · '+cycle.supplier_allocation.source_system,['Pemasok','Volume','Pengangkut'],
        cycle.supplier_allocation.lots.map(lot=>[lot.vendor,lot.units+' unit',lot.carrier??'—']))+
      towerCard('Riwayat negosiasi',line('Catatan tawar-menawar',cycle.negotiation_history.rounds_count)+
        line('Perbandingan ekspedisi',cycle.negotiation_history.carrier_quote_count)+
        '<p><a href="/biz/#negosiasi">Buka rincian dengan kata sandi BIZ</a></p>')+
      tableRows('Jadwal pengiriman · GPS/IoT simulasi',['Vendor','Berangkat','ETA','Tenggat','Perjalanan','Pelacakan'],
        cycle.delivery_schedule.lots.map(lot=>[lot.vendor,'Hari '+lot.dispatch_day,'Hari '+lot.eta_day,
          'Hari '+lot.deadline_day,lot.delivery_route.join(' → '),lot.gps_iot_status]))+
      towerCard('Proyeksi penyelesaian',line('Hari selesai',optionalValue(end.completion_day,'Hari '))+
        line('Margin waktu',optionalValue(end.margin_days))+line('Rencana pemenuhan',end.fulfillment_percent+'%')+
        line('Realisasi pemenuhan',end.realized_percent+'%')+line('Unit lolos / rusak',end.accepted_units+' / '+end.damaged_units)+
        line('Faktur lunas',end.paid_invoices+' / '+end.total_invoices)+line('Status',end.invoice_status==='invoice_hold'?
          'Ditahan untuk koreksi':end.invoice_status==='paid'?'Lunas':'Menunggu'));
  }else $('tower-outputs').innerHTML=towerCard('Rencana pembelian','<p>Jalankan simulasi sampai agen Pengadaan mengirim permintaan penawaran.</p>');
  $('tower-forecast').innerHTML=tableRows('Prakiraan permintaan dan titik pesan',['Produk','EWMA per hari','Prakiraan 3 hari','Safety stock','ROP'],
    snapshot.forecast.map(p=>[p.product,amount(p.daily_ewma),amount(p.forecast_3_days),p.safety_stock,p.dynamic_rop]))+
    tableRows('Bayesian Vendor Scorecard',['Pemasok','Pengiriman','OTD','Defect Rate','Risiko posterior','Grade'],
      snapshot.scorecards.map(s=>[s.vendor,s.shipments,s.otd==null?'—':percent(s.otd),
        s.defect_rate==null?'—':percent(s.defect_rate),percent(s.posterior_risk),s.grade??'—']));
  $('tower-events').innerHTML=tableRows('GS1 EPCIS 2.0 · Aliran simulasi',['EPC lot','Langkah','Disposisi','Sistem sumber','Hari'],
    snapshot.epcis_events.map(event=>[event.epc_id,event.biz_step,event.disposition_code,event.source_system,event.day]));
  $('tower-alerts').innerHTML=tableRows('Anomali rantai pasok',['Kode','Subjek','Skor','Keparahan','Alasan'],
    snapshot.anomaly_alerts.map(event=>[event.code,event.subject,amount(event.score),event.severity,event.reason]));
}

function memoryMarkup(rows, compact=false){
  if(!rows.length)return '<p>Belum ada memori agen pada skenario ini.</p>';
  return '<ul class="agent-memory-list">'+rows.map(entry=>'<li><strong>'+esc(entry.decision)+'</strong><small>'+
    esc((memoryRoles[entry.role]??entry.role)+' · '+entry.subject+' · giliran '+entry.tick+' · hari '+entry.day)+'</small>'+
    (compact?'':'<p>'+esc(entry.reason)+'</p><dl>'+Object.entries(entry.facts).filter(([,value])=>value!=null)
      .map(([key,value])=>'<div><dt>'+esc(key.replaceAll('_',' '))+'</dt><dd>'+esc(value)+'</dd></div>').join('')+'</dl>')+'</li>').join('')+'</ul>';
}

async function refreshMemoryView(){
  const request=++memoryRequest;
  const role=$('tower-memory-role').value;
  try{
    const data=await api('/api/memory'+(role?'/'+role:''));
    if(request===memoryRequest)$('tower-memory-list').innerHTML=towerCard('Memori keputusan',memoryMarkup(data.memory));
  }catch(error){if(request===memoryRequest)$('tower-error').textContent=error.message}
}

async function refreshControlTower(){
  if(towerLoading)return;
  towerLoading=true;
  $('tower-error').textContent='';
  try{
    towerSnapshot=await api('/api/control-tower');
    renderTower();
    if(!$('tower-memory').hidden)await refreshMemoryView();
  }catch(error){$('tower-error').textContent=error.message}
  finally{towerLoading=false}
}

function refreshInspectorMemory(role,tick,node){
  const key=role+':'+tick;
  if(inspectorKey!==key){
    inspectorKey=key;
    inspectorResult=null;
    inspectorRequest=api('/api/memory/'+role).then(data=>data.memory.slice(0,3)).catch(()=>[]);
  }
  const paint=rows=>{
    if(node?.isConnected)node.innerHTML='<h3>Memori terbaru</h3>'+memoryMarkup(rows,true);
  };
  if(inspectorResult){paint(inspectorResult);return;}
  inspectorRequest.then(rows=>{
    if(inspectorKey!==key)return;
    inspectorResult=rows;
    paint(rows);
  });
}

$('tower-cycle').onchange=renderTower;
$('tower-memory-role').innerHTML='<option value="">Semua agen</option>'+Object.entries(memoryRoles)
  .map(([role,name])=>'<option value="'+esc(role)+'">'+esc(name)+'</option>').join('');
$('tower-memory-role').onchange=refreshMemoryView;
const towerButtons=document.querySelectorAll('[data-tower-view]');
for(const button of towerButtons)button.onclick=()=>{
  for(const tab of towerButtons){
    const active=tab===button;
    tab.setAttribute('aria-pressed',String(active));
    $('tower-'+tab.dataset.towerView).hidden=!active;
  }
  if(button.dataset.towerView==='memory')refreshMemoryView();
};
