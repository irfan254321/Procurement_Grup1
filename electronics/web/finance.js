const financeTaxNames={vat:'PPN',pbb:'PBB-P2',pph_badan:'PPh Badan',pph21:'PPh Pasal 21',pph23:'PPh Pasal 23',meterai:'Bea Meterai'};
const expenseNames={payroll:'Gaji',rent:'Sewa gudang',operations:'Operasional'};
const financeMoney=new Intl.NumberFormat('id-ID',{notation:'compact',maximumFractionDigits:1});
let financeState=null, financeBusy=false;

const financeLine=(label,value)=>'<div class="fin-log"><span>'+esc(label)+'</span><strong>'+esc(value)+'</strong></div>';
const financeCards=entries=>entries.map(([label,value])=>
  '<article><span>'+esc(label)+'</span><strong>'+rupiah(value)+'</strong></article>').join('');
const financeRows=rows=>rows.map(([label,value,style])=>'<tr class="'+(style??'')+'"><th scope="row">'+esc(label)+
  '</th><td>'+(value===null?'Belum dicatat':rupiah(value||0))+'</td></tr>').join('');

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
  const lines=cash?[['cash','Saldo kas','#31513d']]:[['sales','Pendapatan','#31513d'],['gross_profit','Laba kotor','#876321']];
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
    return '<span><i style="--legend-color:'+color+'"></i><strong>'+label+'</strong> '+rupiah(last[key])+' <small>('+change+' sejak titik pertama)</small></span>';
  }).join('');
  canvas.setAttribute('aria-label',lines.map(([key,label])=>label+' '+rupiah(last[key])).join(', ')+' · Giliran '+first.tick+' hingga '+last.tick);
}

function financePeriod(id, report){
  const active=report.periods.at(-1);
  const selector=$(id);
  const periods=report.periods.slice(0,-1).reverse();
  const options='<option value="">Bulan '+active.month+' (berjalan)</option>'+
    periods.map(period=>'<option value="'+period.month+'">Bulan '+period.month+'</option>').join('');
  if(selector.dataset.options!==options){
    const value=selector.value;
    selector.innerHTML=options;
    selector.value=periods.some(period=>String(period.month)===value)?value:'';
    selector.dataset.options=options;
  }
  return periods.find(period=>String(period.month)===selector.value)??active;
}

function financeCoverage(period, report){
  const days=financeState.profit_report.days_per_month;
  const firstDay=(period.month-1)*days;
  const endDay=Math.min(financeState.day, firstDay+days-1);
  const startDay=Math.max(firstDay,report.start_day);
  const coverage=report.start_tick>0&&period===report.periods[0]?' · Sejak giliran '+report.start_tick:'';
  return 'Hari '+startDay+'–'+endDay+coverage;
}

function renderProfitReport(){
  const report=financeState.profit_report;
  const period=financePeriod('profit-month',report);
  $('profit-period-details').textContent=financeCoverage(period,report);
  $('expense-period').textContent='Pembayaran mengurangi kas dan dicatat pada bulan '+report.periods.at(-1).month+' · Hari '+financeState.day+'.';
  const netLabel=period.income_tax===null?'Laba bersih sementara':'Laba bersih';
  $('finance-kpis').innerHTML=financeCards([
    ['Penjualan bersih',period.sales],
    ['Laba kotor',period.gross_profit],
    ['Laba usaha',period.operating_profit],
    [netLabel,period.net_profit],
  ]);
  $('profit-rows').innerHTML=financeRows([
    ['Penjualan bersih sebelum PPN',period.sales],
    ['Harga pokok penjualan (HPP)',-period.cogs],
    ['Laba kotor',period.gross_profit,'subtotal'],
    ...Object.entries(expenseNames).map(([kind,label])=>[label,-period.expense_totals[kind]]),
    ['Total beban usaha',-period.operating_expenses,'subtotal'],
    ['Laba usaha',period.operating_profit,'subtotal'],
    ['Beban PPh Badan',period.income_tax===null?null:-period.income_tax],
    [netLabel,period.net_profit,'total'],
  ]);
  $('profit-tax-note').textContent=period.income_tax===null?'PPh Badan belum dibukukan untuk periode ini.':'';
  $('expense-history').innerHTML=period.expenses.length?period.expenses.slice().reverse().map(expense=>
    financeLine(expenseNames[expense.kind]+' · Hari '+expense.day,rupiah(expense.amount))).join(''):'<p>Belum ada beban usaha tercatat.</p>';
}

function renderBalanceSheet(){
  const balance=financeState.balance_sheet;
  $('balance-day').textContent='Posisi pada hari simulasi '+financeState.day;
  $('balance-kpis').innerHTML=financeCards([
    ['Total aset',balance.total_assets],['Total liabilitas',balance.total_liabilities],['Ekuitas',balance.equity],
  ]);
  $('balance-assets').innerHTML=financeRows([
    ['Kas',balance.cash],['Persediaan',balance.inventory_value,'subtotal'],
    ...balance.inventory.map(item=>[item.name+' · '+amount(item.units)+' unit',item.value]),
    ['Kredit PPN',balance.vat_credit],['PPN pembelian dalam verifikasi',balance.pending_input_vat],
    ['Total aset',balance.total_assets,'total'],
  ]);
  $('balance-liabilities').innerHTML=financeRows([
    ['Utang pemasok setelah pemeriksaan',balance.supplier_payable],['PPN terutang',balance.vat_due],
    ['Tagihan pajak lain',balance.assessed_tax_due],['Total liabilitas',balance.total_liabilities,'subtotal'],
    ['Ekuitas simulasi',balance.equity],['Total liabilitas dan ekuitas',balance.total_assets,'total'],
  ]);
}

function renderCashFlow(){
  const report=financeState.cash_flow;
  const period=financePeriod('cash-month',report);
  $('cash-period-details').textContent=financeCoverage(period,report);
  $('cash-rows').innerHTML=financeRows([
    ['Saldo awal',period.opening_cash],['Penerimaan pelanggan',period.customer_receipts],
    ['Pembayaran pemasok',-period.supplier_payments],['Pembayaran beban usaha',-period.operating_payments],
    ['Setoran pajak',-period.tax_payments],['Perubahan kas',period.closing_cash-period.opening_cash,'subtotal'],
    ['Saldo akhir',period.closing_cash,'total'],
  ]);
}

function renderRecentTransactions(){
  const {last_purchase:purchase,last_sale:sale}=financeState;
  const transaction=(title,data,fields)=>'<div><h4>'+title+'</h4>'+
    (data?'<p>'+esc(data.product)+(data.vendor?' · '+esc(data.vendor):'')+'</p>'+
      fields.filter(([,key])=>data[key]!=null).map(([label,key])=>financeLine(label,rupiah(data[key]))).join(''):
      '<p>Belum ada transaksi tercatat.</p>')+'</div>';
  $('transactions').innerHTML=transaction('Pengadaan terakhir',purchase,[
    ['Biaya barang dan ongkir','cost'],['PPN faktur','vat'],['Total faktur','invoice'],['Proyeksi laba kotor','profit'],
  ])+transaction('Penjualan terakhir',sale,[
    ['Penjualan sebelum PPN','revenue'],['HPP','cost'],['Total dibayar pelanggan','total'],['Laba kotor','profit'],
  ]);
}

function renderBizFinance(data){
  financeState=data;
  const tax=data.tax;
  const balance=Math.round((tax.output_vat-tax.input_vat-tax.paid.vat)*10000)/10000;
  $('finance-period').textContent='Hari '+data.day+' · Giliran '+data.tick+' · Rupiah (IDR)';
  $('tax-period').textContent='Pencatatan kumulatif sejak giliran '+tax.since_tick+' · Setoran simulasi';
  renderProfitReport();
  renderBalanceSheet();
  renderCashFlow();
  renderRecentTransactions();
  $('ledger').innerHTML=financeRows([
    ['Saldo kas',data.cash],['Sisa anggaran gaji',data.payroll],['Sisa anggaran operasional',data.operations],
    ['Dana dicadangkan untuk PO',data.reserved],['Cadangan kas',data.reserve],
    ['Sisa anggaran pengadaan',data.fund],['Laba dialokasikan ke restok',data.reinvested??0],
  ]);
  $('tax-paid-total').textContent='Total setoran pajak '+rupiah(Object.values(tax.paid).reduce((sum,value)=>sum+value,0));
  $('vat-summary').innerHTML=financeCards([
    ['PPN masukan · faktur vendor',tax.input_vat],['PPN keluaran · penjualan',tax.output_vat],
    [balance<0?'Saldo kredit PPN':'Sisa PPN untuk disetor',Math.abs(balance)],
  ]);
  $('tax-rows').innerHTML=Object.entries(financeTaxNames).map(([kind,label])=>{
    const paid=tax.paid[kind];
    const due=kind==='vat'?balance:Math.round((tax.assessed[kind]-paid)*10000)/10000;
    const status=due<0?'Kredit '+rupiah(-due):kind!=='vat'&&!tax.assessed[kind]?'Belum diisi':rupiah(due);
    return '<tr><th scope="row">'+label+'</th><td>'+status+'</td><td>'+rupiah(paid)+'</td><td>'+
      (due>0?'<button type="button" class="profile-button" data-tax-pay="'+kind+'">Catat setoran</button>':'—')+'</td></tr>';
  }).join('');
  $('tax-payments').innerHTML=tax.payments.length?tax.payments.map(payment=>
    financeLine(financeTaxNames[payment.kind]+' · Giliran '+payment.tick,rupiah(payment.amount))).join(''):'<p>Belum ada setoran simulasi.</p>';
  requestAnimationFrame(refreshFinanceChart);
}

function refreshFinanceChart(){
  if(financeState&&!$('biz-finance').hidden&&!$('fin-view-kas').hidden)drawFinanceChart(financeState.finance_series);
}

function resetBizFinance(){
  financeState=null;
  for(const id of ['finance-period','finance-kpis','profit-rows','expense-history','profit-period-details','expense-period',
    'profit-tax-note','expense-notice','balance-day','balance-kpis','balance-assets','balance-liabilities','cash-period-details',
    'cash-rows','ledger','transactions','finance-chart-caption','tax-period','vat-summary','tax-paid-total',
    'tax-rows','tax-payments','tax-notice'])$(id).replaceChildren();
  for(const id of ['profit-month','cash-month']){
    $(id).replaceChildren();
    delete $(id).dataset.options;
  }
  $('finance-chart').width=0;
  $('finance-chart').setAttribute('aria-label','Grafik tren keuangan');
  $('expense-form').reset();
  $('tax-assessment').reset();
}

async function submitFinance(action,payload,button,notice){
  if(financeBusy)return false;
  const token=sessionStorage.getItem(tokenKey);
  financeBusy=true;
  button.disabled=true;
  try{
    const {status,data}=await privateRequest('finance',{token,payload:{...payload,action}});
    if(sessionStorage.getItem(tokenKey)!==token)return false;
    if(status===401){
      sessionStorage.removeItem(tokenKey);
      await loadCompanyPrivate();
      authMessage.textContent='Sesi perusahaan berakhir. Masuk kembali.';
      return false;
    }
    if(status!==200)throw new Error(data.error??'Pencatatan belum berhasil.');
    if(privateView==='finance')renderBizFinance(data);
    notice.textContent=action==='expense'?'Pembayaran beban tercatat pada hari '+data.day+'.':
      action==='pay'?'Setoran simulasi tercatat.':'Tagihan tersimpan.';
    return true;
  }catch(error){
    notice.textContent=error.message;
    return false;
  }finally{
    financeBusy=false;
    button.disabled=false;
  }
}

$('profit-month').onchange=renderProfitReport;
$('expense-form').onsubmit=async event=>{
  event.preventDefault();
  const form=event.currentTarget;
  const data=new FormData(form);
  if(await submitFinance('expense',{kind:data.get('kind'),amount:Number(data.get('amount'))},
    form.querySelector('button'),$('expense-notice')))form.elements.amount.value='';
};
$('cash-month').onchange=renderCashFlow;
$('finance-metric').onchange=refreshFinanceChart;
$('tax-assessment').onsubmit=event=>{
  event.preventDefault();
  const data=new FormData(event.currentTarget);
  submitFinance('assessment',{kind:data.get('kind'),amount:Number(data.get('amount'))},
    event.currentTarget.querySelector('button'),$('tax-notice'));
};
$('tax-rows').onclick=event=>{
  const button=event.target.closest('[data-tax-pay]');
  if(button)submitFinance('pay',{kind:button.dataset.taxPay},button,$('tax-notice'));
};
document.querySelectorAll('[data-fin-view]').forEach(button=>button.addEventListener('click',()=>{
  const selected=button.dataset.finView;
  for(const option of document.querySelectorAll('[data-fin-view]')){
    option.setAttribute('aria-pressed',String(option===button));
    $('fin-view-'+option.dataset.finView).hidden=option.dataset.finView!==selected;
  }
  refreshFinanceChart();
}));
window.addEventListener('resize',refreshFinanceChart);
