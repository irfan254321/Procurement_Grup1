const privateSlug=document.body.dataset.companyPath.split('/').filter(Boolean)[0];
const privatePath='/api/companies/'+privateSlug;
const tokenKey='biz-negotiations:'+privateSlug;
const unlockForm=$('company-unlock');
const authMessage=$('company-unlock-message');
const privateData=$('company-private-data');
const lockButton=$('company-lock');
let passwordConfigured=true, privateView='negotiations', privateLoadId=0;

async function privateRequest(path,{payload,token}={}){
  const headers={};
  if(token)headers.Authorization='Bearer '+token;
  if(payload!==undefined)headers['Content-Type']='application/json';
  const response=await fetch(privatePath+'/'+path,{
    method:payload===undefined?'GET':'POST',headers,
    cache:'no-store',
    body:payload===undefined?undefined:JSON.stringify(payload),
  });
  return {status:response.status,data:await response.json()};
}

function privateTable(title,headings,rows){
  return '<article class="company-block"><h2>'+esc(title)+'</h2>'+
    (rows.length?companyTable(title,headings,rows.map(cells=>({cells:cells.map(esc)}))):
      '<p>Belum ada catatan untuk perusahaan ini dalam skenario aktif.</p>')+'</article>';
}

function renderCompanyNegotiations(data){
  const rounds=data.negotiation_history.filter(row=>row.kind==='negotiation');
  const quotes=data.negotiation_history.filter(row=>row.kind==='carrier_quote');
  privateData.innerHTML=privateTable('Jadwal negosiasi',['Siklus','Perusahaan','Tahap','Rencana giliran','Giliran terakhir','Status'],
    data.negotiation_schedule.map(slot=>[slot.cycle,slot.partner,slot.stage,slot.scheduled_tick??'—',
      slot.actual_tick??'—',slot.state]))+
    privateTable('Jadwal pengiriman',['Siklus','Vendor','Rute','Berangkat','ETA','Tenggat','Pelacakan'],
    data.delivery_schedule.map(lot=>[lot.cycle,lot.vendor,lot.delivery_route.join(' → '),'Hari '+lot.dispatch_day,
      'Hari '+lot.eta_day,'Hari '+lot.deadline_day,lot.gps_iot_status]))+
    privateTable('Riwayat tawar-menawar',['Siklus','Giliran','Vendor','Putaran','Aksi','Harga','Alasan'],
      rounds.map(row=>[row.cycle,row.tick,row.vendor,row.round,row.action,rupiah(row.amount),row.reason]))+
    privateTable('Penawaran ekspedisi',['Siklus','Vendor','Pengangkut','Layanan','Hari','Ongkir','Keputusan'],
      quotes.flatMap(row=>{
        const options=row.options??row.orders.flatMap(lot=>lot.options.map(option=>({...option,vendor:lot.vendor})));
        return options.map(option=>[row.cycle,option.vendor,option.carrier,option.name,option.lead_days,
          rupiah(option.freight),option.selected?'Terpilih':option.online===false?'Offline':option.eligible?'Layak':'Di luar batas']);
      }));
}

function hideCompanyPrivate(){
  privateData.hidden=true;
  const finance=$('biz-finance');
  if(finance)finance.hidden=true;
  lockButton.hidden=true;
}

async function loadCompanyPrivate(command=privateView){
  privateView=command;
  const requestId=++privateLoadId;
  hideCompanyPrivate();
  unlockForm.hidden=true;
  authMessage.textContent='Memuat akses perusahaan…';
  try{
    const token=sessionStorage.getItem(tokenKey);
    if(token){
      const {status,data}=await privateRequest(command,{token});
      if(requestId!==privateLoadId)return;
      if(status===200){
        if(command==='finance'){
          renderBizFinance(data);
          $('biz-finance').hidden=false;
        }else{
          renderCompanyNegotiations(data);
          privateData.hidden=false;
        }
        lockButton.hidden=false;
        authMessage.textContent='';
        return;
      }
      if(status!==401)throw new Error(data.error??'Data internal belum tersedia.');
      sessionStorage.removeItem(tokenKey);
    }
    if(typeof resetBizFinance==='function')resetBizFinance();
    const {status,data}=await privateRequest('access');
    if(requestId!==privateLoadId)return;
    if(status!==200)throw new Error(data.error??'Akses perusahaan belum tersedia.');
    passwordConfigured=data.configured;
    $('company-unlock-help').textContent=passwordConfigured
      ?'Masukkan kata sandi perusahaan untuk membuka catatan.'
      :'Buat kata sandi perusahaan pada akses pertama. Gunakan minimal 8 karakter.';
    $('company-password').autocomplete=passwordConfigured?'current-password':'new-password';
    $('company-unlock-submit').textContent=passwordConfigured?'Buka catatan':'Atur sandi & buka';
    privateData.replaceChildren();
    unlockForm.hidden=false;
    authMessage.textContent='';
  }catch(error){if(requestId===privateLoadId)authMessage.textContent=error.message}
}

unlockForm.addEventListener('submit',async event=>{
  event.preventDefault();
  const input=$('company-password'), button=$('company-unlock-submit');
  button.disabled=true;
  try{
    const {status,data}=await privateRequest('access',{payload:{password:input.value,setup:!passwordConfigured}});
    if(status!==200)throw new Error(data.error??'Akses ditolak.');
    sessionStorage.setItem(tokenKey,data.token);
    await loadCompanyPrivate();
  }catch(error){authMessage.textContent=error.message}
  finally{input.value='';button.disabled=false}
});
lockButton.addEventListener('click',async()=>{
  const token=sessionStorage.getItem(tokenKey);
  sessionStorage.removeItem(tokenKey);
  ++privateLoadId;
  privateData.replaceChildren();
  hideCompanyPrivate();
  if(typeof resetBizFinance==='function')resetBizFinance();
  try{if(token)await privateRequest('logout',{token,payload:{}});}
  finally{await loadCompanyPrivate()}
});
