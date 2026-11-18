const financeTaxNames={vat:'PPN',pbb:'PBB-P2',pph_badan:'PPh Badan',pph21:'PPh Pasal 21',pph23:'PPh Pasal 23',meterai:'Bea Meterai'};
const financeMoney=new Intl.NumberFormat('id-ID',{notation:'compact',maximumFractionDigits:1});
let taxBusy=false;

function drawFinanceChart(series){
  const canvas=$('finance-chart');
  const width=canvas.clientWidth;
  if(!width||!series.length)return;
  const height=canvas.clientHeight;
  const dpr=Math.min(window.devicePixelRatio||1,2);
  canvas.width=width*dpr;
  canvas.height=height*dpr;
  const ctx=canvas.getContext('2d');
  ctx.scale(dpr,dpr);
  const cash=$('finance-metric').value==='cash';
  const lines=cash?[['cash','Saldo kas','#256c9b']]:[['sales','Pendapatan','#256c9b'],['gross_profit','Laba kotor','#087d64']];
  const values=series.flatMap(point=>lines.map(([key])=>point[key]));
  const low=cash?Math.min(...values)*.96:Math.min(0,...values);
  const high=Math.max(low+1,Math.max(...values)*1.07);
  const left=66,right=width-22,top=15,bottom=height-29;
  const first=series[0],last=series.at(-1);
  const x=tick=>left+(right-left)*(tick-first.tick)/Math.max(1,last.tick-first.tick);
  const y=value=>bottom-(value-low)/(high-low)*(bottom-top);
  ctx.font='11px system-ui';
  for(let i=0;i<=4;i++){
    const value=low+(high-low)*i/4;
    const row=y(value);
    ctx.strokeStyle='#e0ebe9';
    ctx.beginPath();ctx.moveTo(left,row);ctx.lineTo(right,row);ctx.stroke();
    ctx.fillStyle='#4d6266';
    ctx.fillText(financeMoney.format(value*10000),5,row+4);
  }
  ctx.fillText('Giliran '+first.tick,left,height-7);
  if(last.tick!==first.tick){
    ctx.textAlign='right';ctx.fillText(last.tick,right,height-7);ctx.textAlign='left';
  }
  for(const [key,,color] of lines){
    ctx.strokeStyle=color;ctx.fillStyle=color;ctx.lineWidth=2.5;
    ctx.beginPath();
    series.forEach((point,index)=>{
      if(index)ctx.lineTo(x(point.tick),y(point[key]));
      else ctx.moveTo(x(point.tick),y(point[key]));
    });
    ctx.stroke();
    ctx.beginPath();ctx.arc(x(last.tick),y(last[key]),4,0,Math.PI*2);ctx.fill();
  }
  $('finance-chart-caption').innerHTML=lines.map(([key,label,color])=>{
    const delta=Math.round((last[key]-first[key])*10000)/10000;
    const change=(delta>0?'+':'')+rupiah(delta);
    return '<span><i style="background:'+color+'"></i><strong>'+label+'</strong> '+rupiah(last[key])+' <small>('+change+' sejak titik pertama)</small></span>';
  }).join('');
  canvas.setAttribute('aria-label',lines.map(([key,label])=>label+' '+rupiah(last[key])).join(', ')+' · Giliran '+first.tick+' hingga '+last.tick);
}

function renderFinance(){
  if(!world?.tax||$('profit').hidden)return;
  const tax=world.tax;
  const balance=Math.round((tax.output_vat-tax.input_vat-tax.paid.vat)*10000)/10000;
  $('finance-period').textContent='Simulasi BIZ District · Giliran '+world.tick;
  $('tax-period').textContent='Pencatatan kumulatif sejak giliran '+tax.since_tick+' · Setoran simulasi';
  $('finance-kpis').innerHTML=[
    ['Pendapatan sebelum PPN',world.sales],
    ['Laba kotor',world.sales-world.cogs],
    ['Saldo kas',world.cash],
    ['Total setoran pajak',Object.values(tax.paid).reduce((sum,value)=>sum+value,0)],
  ].map(([label,value])=>'<article class="card"><span>'+label+'</span><strong>'+rupiah(value)+'</strong></article>').join('');
  $('vat-summary').innerHTML=[
    ['PPN masukan · faktur vendor',tax.input_vat],['PPN keluaran · penjualan',tax.output_vat],
    [balance<0?'Saldo kredit PPN':'Sisa PPN untuk disetor',Math.abs(balance)],
  ].map(([label,value])=>'<div><small>'+label+'</small><strong>'+rupiah(value)+'</strong></div>').join('');
  $('tax-rows').innerHTML=Object.entries(financeTaxNames).map(([kind,label])=>{
    const paid=tax.paid[kind];
    const due=kind==='vat'?balance:Math.round((tax.assessed[kind]-paid)*10000)/10000;
    const status=due<0?'Kredit '+rupiah(-due):kind!=='vat'&&!tax.assessed[kind]?'Belum diisi':rupiah(due);
    return '<tr><th scope="row">'+label+'</th><td>'+status+'</td><td>'+rupiah(paid)+'</td><td>'+
      (due>0?'<button type="button" data-tax-pay="'+kind+'"'+(taxBusy?' disabled':'')+'>Catat setoran</button>':'—')+'</td></tr>';
  }).join('');
  $('tax-payments').innerHTML=tax.payments.length?tax.payments.map(payment=>
    line(financeTaxNames[payment.kind]+' · Giliran '+payment.tick,rupiah(payment.amount))).join(''):'<p>Belum ada setoran simulasi.</p>';
  drawFinanceChart(world.finance_series);
}

async function taxRequest(path,payload){
  if(taxBusy)return;
  taxBusy=true;
  const submit=$('tax-assessment').querySelector('button');
  submit.disabled=true;
  try{
    // Use the same request lock as simulation ticks so finance cannot render stale responses.
    if(await change('/api/tax/'+path,payload))$('tax-notice').textContent=path==='pay'?'Setoran simulasi tercatat.':'Tagihan tersimpan.';
    else $('tax-notice').textContent='Simulasi sedang berganti giliran. Coba lagi.';
  }catch(error){$('tax-notice').textContent=error.message}
  finally{taxBusy=false;submit.disabled=false;renderFinance()}
}

$('finance-metric').onchange=renderFinance;
$('tax-assessment').onsubmit=event=>{
  event.preventDefault();
  const data=new FormData(event.currentTarget);
  taxRequest('assessment',{kind:data.get('kind'),amount:Number(data.get('amount'))});
};
$('tax-rows').onclick=event=>{
  const button=event.target.closest('[data-tax-pay]');
  if(button)taxRequest('pay',{kind:button.dataset.taxPay});
};
window.addEventListener('resize',()=>{if(world?.tax&&!$('profit').hidden)drawFinanceChart(world.finance_series)});
