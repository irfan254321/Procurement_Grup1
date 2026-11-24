const floorRooms = {
  buyer:{title:'Lobi pelanggan', subtitle:'Area kedatangan dan konsultasi produk', color:'#51a692', floor:'#d2e8df',
    staff:[['Mencatat kedatangan dan arahkan pelanggan ke toko.',2.5,2.2],['Membantu pelanggan memahami pilihan Laptop, Monitor, dan Printer.',7.9,2.4]]},
  seller:{title:'Toko elektronik', subtitle:'Ruang pamer dan kasir', color:'#5099b1',floor:'#c9e0e8',
    staff:[['Menilai pesanan dan mengecek stok yang tersedia.',8.5,2.4],['Menyiapkan barang dari ruang pamer.',3.1,4.4],['Mencatat omzet dan harga pokok saat pesanan terjual.',8.1,5.7]]},
  stock:{title:'Gudang', subtitle:'Inventaris dan penerimaan barang', color:'#7394b9',floor:'#d0dbe6',
    staff:[['Memeriksa stok dan memicu permintaan restok.',7.9,2.5],['Mencocokkan barang masuk dengan pesanan pengadaan.',8.1,5.4],['Menata barang yang tersedia di rak.',3.5,4.4]]},
  finance:{title:'Keuangan', subtitle:'Kas, anggaran, dan laba pengadaan', color:'#947bc1',floor:'#ded6ea',
    staff:[['Memutuskan kelayakan dari kas bebas, anggaran, dan proyeksi laba.',3.5,2.5],['Memantau anggaran pengadaan dan dana yang dicadangkan.',7.5,2.9],['Memantau pembayaran saat barang diterima.',7.5,5.6]]},
  procurement:{title:'Pengadaan', subtitle:'Permintaan restok dan perbandingan pemasok', color:'#bc834f',floor:'#eddec8',
    staff:[['Mengundang dan membandingkan pemasok untuk restok.',3.5,2.5],['Membandingkan hasil penawaran final vendor.',7.5,2.9],['Menyiapkan rincian jumlah barang untuk pengadaan.',7.5,5.6]]},
  deal:{title:'Ruang negosiasi', subtitle:'Penawaran, tawar balik, dan kesepakatan', color:'#be797e',floor:'#ecd4d9',
    staff:[['Menilai tawaran dan batas harga pembeli.',4.2,4.2],['Mencatat nilai tawaran terakhir dan hasil pembicaraan.',8.1,4.6]]},
  vendor:{title:'Kantor vendor', subtitle:'Penawaran pemasok dan persiapan pesanan', color:'#608c73',floor:'#d6e4d6',
    staff:[['Menilai tawaran berdasarkan harga minimum dan kapasitas.',3.5,2.5],['Menyiapkan dan mengirim pesanan vendor.',7.5,5.6]]},
  carrier:{title:'Terminal logistik', subtitle:'Penjemputan di pemasok dan pengantaran ke Gudang BIZ',color:'#467787',floor:'#d7e7e9',
    staff:[['Memeriksa muatan, rute, dan jadwal pengiriman.',3.5,2.5],['Menjemput barang dan menyerahkannya ke gudang tujuan.',7.5,5.6]]},
};

let roomKey = null;
let sceneSignature = '';
let roomPerson = '';
let room3D;
let room3DLoading;

function loadRoom3D(){
  if(room3DLoading||typeof window==='undefined'||!window.WebGL2RenderingContext)return;
  room3DLoading=import('/room-3d.mjs').then(async({createRoom3D})=>{
    room3D=await createRoom3D();
    sceneSignature='';
    renderInterior();
  }).catch(error=>console.warn('Interior 2D digunakan.',error));
}

function roomOrders(state){
  const serving=state.phase==='seller'&&state.case?.id&&!state.case.restocked?state.case:null;
  return [
    ...(serving?[{...serving,room:'seller',status:'Sedang dilayani'}]:[]),
    ...(state.queue??[]).filter(c=>!c.restocked).map(c=>({...c,room:'buyer',status:'Antre di lobi'})),
  ];
}

function roomAction(role,event){
  if(!event)return null;
  if(role==='carrier')return [event.inspection?'Serah terima dicatat':event.shipment==='shipping'?
    'Menjemput dan mengantar kiriman':'Menyiapkan rute dan jadwal penjemputan','▤',0];
  const inspectionActions={
    inspected:['Memeriksa jumlah dan kondisi barang','📦',1],
    invoice_hold:['Menahan pembayaran dan meminta koreksi','▥',2],
    invoice_corrected:['Mengirim faktur yang sudah dikoreksi','✉',0],
    paid:['Mencocokkan hasil pemeriksaan dan membayar faktur','▥',2],
  };
  if(event.inspection)return inspectionActions[event.inspection.state]??[event.title,'▥',0];
  const title=event.title;
  if(role==='buyer')return ['Menyambut pelanggan','🎫',0];
  if(role==='seller')return title==='Penjualan berhasil'?['Memindai barang dan mencetak struk','🧾',2]:['Memeriksa pesanan pelanggan','▤',0];
  if(role==='stock')return event.shipment==='delivered'?['Memindahkan kardus ke gudang','📦',1]:['Mengecek rak dan stok','▤',0];
  if(role==='finance')return [title==='Pembelian disetujui'?'Mencadangkan dana pengadaan':'Memeriksa kas dan anggaran','▥',0];
  if(role==='procurement')return title==='Permintaan penawaran'?['Mengirim permintaan ke vendor','✉',0]:['Membandingkan penawaran vendor','▥',1];
  if(role==='deal')return ['Bertukar penawaran di meja rapat','▤',0];
  if(event.shipment==='packing')return ['Mengemas pesanan','📦',1];
  if(event.shipment==='shipping')return ['Menyerahkan kardus untuk dikirim','📦',1];
  return ['Meninjau tawaran harga','▤',0];
}

function roomPeople(role, room, state, currentEvent, roomIdentity=role) {
  const seed=[...roomIdentity].reduce((sum,letter)=>sum+letter.charCodeAt(0),0);
  const appearance=variant=>({variant,gender:variant%2?'female':'male'});
  const activeOrder = state.phase==='seller' && state.case?.id ? state.case : null;
  const staff = room.staff.map(([task,x,y],i)=>({
    ...appearance(seed+i),
    id:'staff-'+i,name:roomRoleNames[role][i],job:roomRoleNames[role][i],task,duties:roomDuties[role]?.[i],x,y,
    live:i===0 && role!=='buyer',
  }));
  if(role==='deal' && currentEvent?.meeting)staff.push({
    ...appearance(seed+staff.length),
    id:'visitor',name:currentEvent.meeting.vendor,job:'Agent Perwakilan Vendor',
    task:'Membahas tawaran pengadaan dengan PT. Biz Indonesia Market.',
    x:6.7,y:2.6,live:true,
  });
  const orders=roomOrders(state).filter(order=>order.room===role);
  if(role==='seller'&&currentEvent?.tick===state.tick&&currentEvent.title==='Penjualan berhasil'&&currentEvent.customer){
    orders.unshift({...currentEvent.customer,status:'Baru membayar'});
  }
  const customers=orders.map((order,i)=>({
    ...appearance(order.id),
    id:'customer-'+order.id,name:'Pelanggan '+order.id,job:order.status,
    task:order.quantity+' × '+order.product+' · batas bayar '+rupiah(order.budget)+' per unit.',
    x:order.id===activeOrder?.id||order.status==='Baru membayar'?7.1:1.4+(i%8)*1.05,y:3.9+Math.floor(i/8)*.87,
    buyerPrediction:order.prediction,
    enters:role==='buyer'&&currentEvent?.customers?.some(c=>c.id===order.id),
    called:role==='seller'&&order.id===activeOrder?.id,
  }));
  return {staff,customers};
}

const roomPoint=(x,y,z=0)=>[390+(x-y)*36,189+(x+y)*18-z];
function roomPolygon(points,fill,stroke=''){
  return '<polygon points="'+points.map(p=>roomPoint(...p).join(',')).join(' ')+'" fill="'+fill+'"'+(stroke?' stroke="'+stroke+'"':'')+'/>';
}
function roomTile(x,y,w,d,z,fill,stroke){
  return roomPolygon([[x,y,z],[x+w,y,z],[x+w,y+d,z],[x,y+d,z]],fill,stroke);
}
function roomBox(x,y,w,d,h,top,front,side,z=0){
  return roomPolygon([[x,y+d,z],[x+w,y+d,z],[x+w,y+d,z+h],[x,y+d,z+h]],front)+
    roomPolygon([[x+w,y,z],[x+w,y+d,z],[x+w,y+d,z+h],[x+w,y,z+h]],side)+
    roomTile(x,y,w,d,z+h,top);
}
function roomDesk(x,y,color) {
  return roomBox(x,y,1.6,.75,21,'#dfc8a7','#8e735e','#745e53')+
    roomBox(x+.2,y+.15,.56,.12,14,'#657b85','#233d4a','#152a37',21)+
    roomBox(x+1,y+.37,.39,.27,2,color,'#f5f4eb','#d8d0c2',21);
}
function roomShelf(x,y,boxes){
  let furniture=roomBox(x,y,1.9,.62,44,'#a8bfc2','#446373','#3d5361');
  for(const z of [8,23,38]) for(let i=0;i<3;i++){
    furniture+=roomBox(x+.13+i*.57,y+.53,.37,.14,8,boxes?'#f0c384':'#d8f3f4',boxes?'#bf8759':'#7298a7','#546973',z);
  }
  return furniture;
}
function roomPlant(x,y){
  const [px,py]=roomPoint(x,y,3);
  return '<g transform="translate('+px+' '+py+')"><path d="M-7-9H7L5 2H-5Z" fill="#aa765e"/><path d="M0-8Q-15-11-12-23Q-2-22 0-10Q0-28 12-26Q13-16 0-8" fill="#5b9475"/></g>';
}

function drawRoom(room,role,people){
  let svg='<svg class="floor-art" viewBox="0 0 940 550" aria-hidden="true">'+
    '<defs><linearGradient id="room-bg" x2="0" y2="1"><stop stop-color="#e7eeec"/><stop offset="1" stop-color="#f6f8f4"/></linearGradient></defs>'+
    '<rect width="940" height="550" fill="url(#room-bg)"/>';
  svg+=roomBox(0,0,11,8,9,room.floor,'#91a9a5','#738e92',-9);
  for(let x=0;x<11;x++)for(let y=0;y<8;y++)svg+=roomTile(x,y,1,1,.2,room.floor,'#ffffff6c');
  svg+=roomPolygon([[0,0,0],[0,8,0],[0,8,104],[0,0,104]],'#55727a')+
    roomPolygon([[0,0,0],[11,0,0],[11,0,104],[0,0,104]],'#344e5b');
  for(const x of [1,4.45,8]) {
    svg+=roomPolygon([[x,0,29],[x+2,0,29],[x+2,0,84],[x,0,84]],'#b4e5e6','#d8f2eb')+
      roomPolygon([[x,0,48],[x+2,0,48],[x+2,0,51],[x,0,51]],'#81acb0')+
      roomPolygon([[x+1,0,29],[x+1.06,0,29],[x+1.06,0,84],[x+1,0,84]],'#81acb0');
  }
  for(const y of [2,4,6])svg+=roomPolygon([[0,y,29],[0,y+1.15,29],[0,y+1.15,67],[0,y,67]],room.color,'#d6e2da');
  svg+=roomTile(2,4.7,6.8,2.5,1,'#ffffff60');
  const objects=[[2,()=>roomPlant(1.15,.85)],[10,()=>roomPlant(9.3,1.1)],[15,()=>roomPlant(8.6,6.5)]];
  const place=(x,y,draw)=>objects.push([x+y,()=>draw(x,y)]);
  if(role==='stock'||role==='seller'){
    for(const [x,y] of [[1.2,1.2],[4.2,1.2],[1.2,3]])place(x,y,(a,b)=>roomShelf(a,b,role==='stock'));
    place(7,3.4,(a,b)=>roomDesk(a,b,room.color));
  }else if(role==='deal'){
    place(3.4,2.8,(x,y)=>roomBox(x,y,3.7,1.2,23,'#d7b68f','#957258','#745c54')+
      roomBox(x+1.4,y+.29,1,.65,2,'#f6f3e3','#d5dddf','#c5c8c4',23));
    place(7.4,1.1,roomShelf);
  }else if(role==='buyer'){
    place(2.3,2.7,(x,y)=>roomDesk(x,y,room.color));
    place(6.1,2,(x,y)=>roomBox(x,y,2.4,.8,16,'#8ab2a2','#668c80','#4d6f68'));
  }else{
    for(const [x,y] of [[2.2,2.8],[6.2,3.2],[6.2,5.7]])place(x,y,(a,b)=>roomDesk(a,b,room.color));
  }
  const props={carry:'📦',scan:'▤',stamp:'✓',mail:'✉'};
  const tones=['#bd8262','#ecb989','#9c654e','#e2a67f'];
  const suits=[room.color,'#2b6380','#b96875','#8466a1','#688548'];
  people.forEach((p,i)=>place(p.x,p.y,(x,y)=>{
    const [px,py]=roomPoint(x,y,0),skin=tones[i%tones.length],shirt=suits[i%suits.length];
    const walking=p.jobMotion?.to&&p.live;
    const entering=p.enters||p.called;
    const destination=walking?roomPoint(...p.jobMotion.to):null;
    const moving=walking?' class="floor-move" style="--dx:'+(destination[0]-px)+'px;--dy:'+(destination[1]-py)+'px"':entering?' class="floor-enter" style="--dx:-82px;--dy:46px;animation-delay:'+(i%8)*70+'ms"':'';
    return '<g transform="translate('+px+' '+py+')"><g'+moving+'><ellipse cy="1" rx="13" ry="6" fill="#243f4b30"/><g class="'+(p.live?'floor-worker':'')+'">'+
      '<path d="M-8-17L-8-2L-12 0H-3L0-15L4-1H11L8-5L8-17" fill="#294459"/>'+
      '<path d="M-10-32Q0-37 10-32L9-16H-9Z" fill="'+shirt+'"/>'+
      '<path d="M-8-30L-13-21" stroke="'+shirt+'" stroke-width="6" stroke-linecap="round"/>'+
      '<g class="'+(p.live?'floor-arm':'')+'"><path d="M8-30L14-23" stroke="'+shirt+'" stroke-width="6" stroke-linecap="round"/>'+
      '<path d="M14-23L17-25" stroke="'+skin+'" stroke-width="4" stroke-linecap="round"/></g>'+
      (p.live&&props[p.jobMotion.kind]?'<g transform="translate(20 -25)"><text fill="#22544d" font-size="21">'+props[p.jobMotion.kind]+'</text></g>':'')+
      (p.gender==='female'?'<path d="M-10-40Q-13-50 0-52Q13-52 11-34L9-27L-10-30Z" fill="#30404a"/>':'')+
      '<circle cy="-40" r="9" fill="'+skin+'"/><path d="M-9-39Q-13-50 0-51Q11-50 9-41L3-46L-7-41Z" fill="#30404a"/>'+
      '<path d="M1-34l4-1" stroke="#7a5150" stroke-width="1.4"/>'+
      (p.live?'<path d="M0-70L7-62L0-54L-7-62Z" fill="#a7df62" stroke="#476d38"/>':'')+'</g></g></g>';
  }));
  objects.sort((a,b)=>a[0]-b[0]).forEach(([,draw])=>svg+=draw());
  return svg+'</svg>';
}

const displayProductArtwork={
  Laptop:'<path d="M14 13h51a3 3 0 0 1 3 3v29H11V16a3 3 0 0 1 3-3Z" fill="#24394c"/><path d="M15 17h49v24H15z" fill="#71c1ba"/><path d="M11 45h57l12 9a3 3 0 0 1-2 5H2a2 2 0 0 1-1-4z" fill="#a3b7bc"/><path d="M22 49h36l4 3H18zM32 54h16l3 2H29z" fill="#5b7680"/>',
  Monitor:'<rect x="7" y="8" width="66" height="36" rx="4" fill="#24394c"/><rect x="11" y="12" width="58" height="27" rx="1" fill="#71c1ba"/><path d="M36 44h8v8h15v4H21v-4h15z" fill="#506a76"/><circle cx="65" cy="42" r="1" fill="#a4eabe"/>',
  Printer:'<path d="M23 7h34v26H23z" fill="#f6faf8" stroke="#738e91"/><path d="M29 14h22M29 20h22M29 26h13" stroke="#9cb4b3" stroke-width="2"/><rect x="8" y="22" width="64" height="30" rx="5" fill="#a4bcbd"/><path d="M8 38h64v8a6 6 0 0 1-6 6H14a6 6 0 0 1-6-6z" fill="#4d6974"/><path d="M22 39h36v4H22z" fill="#253a4a"/><path d="M24 43h32l4 14H20z" fill="#f7f8ef"/><circle cx="64" cy="30" r="2" fill="#2c8d6b"/>',
};

function showRoomProducts(role,products){
  const panel=$('floor-showroom');
  panel.hidden=role!=='buyer'&&role!=='seller';
  if(panel.hidden)return;
  panel.innerHTML='<h3>Etalase elektronik</h3><ul class="showroom-products">'+products.map(product=>
    '<li class="showroom-product"><svg viewBox="0 0 80 64" aria-hidden="true">'+(displayProductArtwork[product.name]??'')+
    '</svg><div><strong>'+esc(product.name)+'</strong><span>'+esc(customerPriceLabel(product.retail))+' / unit</span><small class="'+
    (product.units>0?'product-available':'product-out')+'">'+
    (product.units>0?esc(product.units)+' unit tersedia':'Stok habis')+'</small></div></li>').join('')+'</ul>';
}

function renderInterior() {
  if(!roomKey||!world||!models||$('world').hidden)return;
  const vendor=vendors[roomKey],carrier=carriers[roomKey];
  const role=carrier?'carrier':vendor?'vendor':roomKey,room=floorRooms[role];
  if(!room)return;
  const ownShipments=e=>(e?.shipments??[]).filter(order=>carrier?order.route?.carrier===roomKey:order.vendor===roomKey);
  const belongs=e=>carrier?ownShipments(e).length>0||e.inspection?.carrier===roomKey:
    vendor?e.role==='vendor'&&(e.meeting?.vendor===roomKey||e.vendor===roomKey||e.inspection?.vendor===roomKey||ownShipments(e).length>0):
    role==='deal'?e.role==='deal'||!!e.meeting:role==='finance'?e.role==='finance'||(e.shipment==='delivered'&&!e.inspection):e.role===role;
  const event=world.history.find(belongs);
  const liveEvent=world.history[0];
  const {staff,customers}=roomPeople(role,room,world,event,roomKey);
  const offline=!!(vendor||carrier)&&!companyOnline(roomKey);
  const onDuty=!offline&&!!liveEvent&&belongs(liveEvent);
  const jobs=roomJobs(role,event,onDuty);
  if(offline)for(const id of Object.keys(jobs))jobs[id]={kind:'idle',label:'Di luar kantor · perusahaan offline'};
  const roster=[...staff,...customers].map(person=>({...person,offline,jobMotion:jobs[person.id]}));
  const selectedPerson=roster.find(p=>p.id===roomPerson)??roster[0];
  roomPerson=selectedPerson.id;
  const floorName=carrier?room.title:vendor?roomKey:'Lantai '+(offices[role].level+1)+' · '+room.title;
  $('floor-title').textContent=floorName;
  $('floor-subtitle').textContent=room.subtitle;
  $('floor-status').textContent=offline?'Offline · perusahaan tutup':onDuty?'Sedang bertugas':'Giliran '+world.tick;
  const availability=$('room-company-offline');
  availability.hidden=!companySlug(roomKey)||!(vendor||carrier);
  availability.textContent=offline?'Aktifkan perusahaan':'Jadikan offline';
  availability.setAttribute('aria-pressed',String(offline));
  $('floor-tabs').value=roomKey;
  if(!renderCompanyDashboard(vendor||carrier ? roomKey : null))return;
  const action=roomAction(role,event);
  const moveCustomers=!!liveEvent&&(onDuty||world.phase==='seller'&&role==='seller');
  const stockState=['buyer','seller','stock'].includes(role)?world.products.map(p=>p.units):null;
  const signature=JSON.stringify([roomKey,offline,onDuty?liveEvent.tick:null,roomPerson,roster.map(p=>[p.id,p.job]),stockState]);
  const focused=document.activeElement;
  const focusContainer=focused?.closest('#floor-drawing,#floor-roster');
  const rosterScroll=$('floor-roster').scrollTop;
  if(signature!==sceneSignature){
    sceneSignature=signature;
    renderRoomDrawing(room,role,roster,moveCustomers,onDuty?event.tick:null);
  }
  const activity=$('floor-activity');
  const shipments=(vendor||carrier)?ownShipments(event):[];
  const activityDetail=shipments.length?shipments.map(order=>
    (carrier?order.vendor:order.route?.carrier??'Pengangkut')+' · '+amount(order.quantity)+' unit').join(' • '):event?.detail;
  const replayFocused=document.activeElement?.id==='floor-replay';
  activity.innerHTML=event?'<div><small>'+esc(onDuty?'Aktivitas giliran ini':'Aktivitas terakhir · Giliran '+event.tick)+
    '</small><strong>'+esc(onDuty?action[0]:event.title)+'</strong><small>'+esc(activityDetail)+'</small></div>'+
    '<button id="floor-replay">Putar ulang</button>':'<small>Belum ada aktivitas simulasi di ruangan ini.</small>';
  if(event){
    const replay=$('floor-replay');
    replay.onclick=()=>{
      const replayJobs=roomJobs(role,event,!offline);
      renderRoomDrawing(room,role,roster.map(p=>({...p,jobMotion:replayJobs[p.id]})),true,event.tick,true);
    };
    replay.disabled=offline;
    if(replayFocused)replay.focus({preventScroll:true});
  }
  $('floor-roster').innerHTML=roster.map(p=>'<button class="floor-member'+(p.id===roomPerson?' chosen':'')+'" data-person="'+esc(p.id)+'" aria-pressed="'+(p.id===roomPerson)+'"><span>'+esc(p.name.slice(0,1))+'</span><span><strong>'+esc(p.name)+'</strong>'+(p.job!==p.name?'<small>'+esc(p.job)+'</small>':'')+(p.jobMotion?'<small class="floor-job-state">'+esc(p.jobMotion.label)+'</small>':'')+'</span></button>' ).join('');
  $('floor-roster').scrollTop=rosterScroll;
  if(focusContainer&&focused.dataset.person){
    [...focusContainer.querySelectorAll('[data-person]')].find(b=>b.dataset.person===focused.dataset.person)?.focus({preventScroll:true});
  }
  const showActivity=selectedPerson.id==='staff-0'||selectedPerson.id==='visitor';
  const customer=selectedPerson.id.startsWith('customer-');
  const model=customer?models.benchmark.agents.buyer.main:
    selectedPerson.id==='staff-0'&&role!=='buyer'?models.benchmark.agents[role]?.main:null;
  $('floor-agent').innerHTML=carrier?'<strong>Tim logistik</strong><span>Penjemputan, pemuatan, dan serah terima kiriman</span>':
    '<strong>'+esc(models.roles[role][0])+'</strong><span>'+esc(models.roles[role][1])+
    '</span><small>Model · '+esc(models.benchmark.agents[role].main)+'</small>';
  $('floor-roster-title').textContent=vendor||carrier?'Agen di ruangan':'Orang di ruangan';
  const ownOrders=vendor||carrier?companyOrders(roomKey):[];
  const order=ownOrders.find(order=>order.status!=='paid')??ownOrders[0];
  const shippingAgent=(vendor||carrier)&&selectedPerson.id==='staff-1';
  const orderParty=carrier?order?.vendor:order?.route?.carrier;
  const orderSummary=order?[order.id,`${amount(order.quantity)} unit ${order.product??'elektronik'}`,orderParty].filter(Boolean).join(' · '):'';
  $('floor-person').innerHTML='<h3>'+esc(selectedPerson.name)+'</h3>'+(selectedPerson.job!==selectedPerson.name?'<small>'+esc(selectedPerson.job)+'</small>':'')+
    '<p>'+esc(selectedPerson.task)+'</p>'+
    (selectedPerson.duties?'<div class="floor-tasks"><h4>Tugas di '+esc(roomKey)+'</h4><ul>'+
      selectedPerson.duties.map(task=>'<li>'+esc(task)+'</li>').join('')+'</ul></div>':'')+
    (selectedPerson.jobMotion?'<p class="floor-job-state">'+esc(selectedPerson.jobMotion.label)+'</p>':'')+
    (shippingAgent?'<div class="decision"><small>Kiriman '+esc(roomKey)+'</small>'+
      (order?'<strong>'+esc(orderSummary)+'</strong><p>'+esc(companyOrderStatus[order.status])+'</p>':'<p>Belum ada kiriman tercatat.</p>')+'</div>':'')+
    (model?'<p class="floor-model">Model · '+esc(model)+'</p>':'')+
    (customer&&typeof selectedPerson.buyerPrediction==='boolean'?'<p>Prediksi Agent Pembeli · '+(selectedPerson.buyerPrediction?'Beli':'Lewat')+'</p>':'')+
    (showActivity&&event?'<div class="decision"><small>Aktivitas terakhir · Giliran '+event.tick+'</small><strong>'+esc(event.title)+'</strong><p>'+esc(activityDetail)+'</p>'+
      (event.prediction&&event.role===role?'<small>Prediksi · '+esc(event.prediction)+'</small>':'')+'</div>':'');
  let facts='';
  showRoomProducts(role,world.products);
  if(role==='stock')facts=world.products.map(p=>line(p.name,p.units?p.units+' unit':'Stok kosong')).join('');
  if(role==='buyer')facts=line('Antre di lobi',customers.length);
  if(role==='finance')facts='<a class="company-title-link" href="/biz/#keuangan">Buka portal keuangan BIZ →</a>';
  if(carrier)facts=ownOrders.slice(0,4).map(order=>line(order.id,
    order.vendor+' → Gudang BIZ · '+companyOrderStatus[order.status])).join('');
  if(role==='deal'||role==='procurement'||role==='vendor'){
    const offers=world.case?.offers??[];
    facts=offers.filter(o=>!vendor||o.vendor===roomKey).map(o=>line(o.vendor,o.accepted?'Sepakat':'Gagal sepakat')).join('');
    if(vendor&&world.suppliers?.[roomKey])facts=supplierFacts(world.suppliers[roomKey])+facts;
  }
  $('floor-facts').innerHTML=facts;
}

function renderRoomDrawing(room,role,people,moveCustomers,activityKey,replay){
  const roomStyle=role==='carrier'?'vendor':role;
  const drawing=$('floor-drawing');
  const cast=people.map(p=>({...p,live:p.jobMotion?.kind!=='idle'&&!!p.jobMotion,
    enters:moveCustomers&&p.enters,called:moveCustomers&&p.called}));
  const names=people.map(p=>{
    const [x,y]=roomPoint(p.x,p.y,56);
    const customer=p.id.startsWith('customer-');
    const label=customer?'#'+p.id.slice(9):p.job;
    const task=p.jobMotion?.kind!=='idle'?p.jobMotion?.label:null;
    return '<button class="floor-pin'+(p.id===roomPerson?' chosen':'')+'" style="left:'+(100*x/940)+'%;top:'+(100*y/550)+
      '%" data-person="'+esc(p.id)+'" aria-label="'+esc(p.name)+'" aria-pressed="'+(p.id===roomPerson)+'">'+esc(label)+
      (task?'<small>'+esc(task)+'</small>':'')+'</button>';
  }).join('');
  if(room3D){
    if(!$('room-3d-mount'))drawing.innerHTML='<div id="room-3d-mount"></div><div id="room-3d-products" aria-hidden="true"></div><div id="room-3d-labels"></div>';
    $('room-3d-labels').innerHTML=names;
    const pins=new Map([...$('room-3d-labels').children].map(pin=>[pin.dataset.person,pin]));
    room3D.update($('room-3d-mount'),$('room-3d-products'),roomKey,room,role,cast.map(p=>({...p,pin:pins.get(p.id)})),
      activityKey,replay,world.products,carriers[roomKey]?.color??room.color);
  }else{
    const present=cast.filter(person=>!person.offline);
    drawing.innerHTML=drawRoom(room,roomStyle,present)+(present.length?names:'');
  }
}

function openInterior(key, focus=true){
  if(!offices[key]&&!vendors[key]&&!carriers[key])return;
  sceneSignature='';
  roomKey=key;
  selected=key;
  roomPerson='';
  $('map').hidden=true;
  $('floor-view').hidden=false;
  $('floor-tabs').innerHTML=Object.entries(offices).map(([k,o])=>'<option value="'+esc(k)+'">Lantai '+(o.level+1)+' · '+esc(floorRooms[k].title)+'</option>').join('')+
    '<optgroup label="Pemasok">'+Object.keys(vendors).map(name=>'<option value="'+esc(name)+'">'+esc(name)+'</option>').join('')+'</optgroup>'+
    '<optgroup label="Pengangkut">'+Object.keys(carriers).map(name=>'<option value="'+esc(name)+'">'+esc(name)+'</option>').join('')+'</optgroup>';
  renderInterior();
  if(!$('company-room').hidden)loadRoom3D();
  if(focus)$('floor-tabs').focus();
}

function closeInterior(){
  if(!roomKey)return;
  const previous=roomKey;
  roomKey=null;
  resetCompanyDashboard();
  room3D?.stop();
  $('floor-view').hidden=true;
  $('map').hidden=false;
  district3D?.update(world);
  if(district3D&&offices[previous])$('biz-tower-badge').focus();
  else [...$('markers').children].find(b=>b.dataset.role===previous)?.focus();
}

$('floor-back').onclick=closeInterior;
$('floor-tabs').onchange=()=>openInterior($('floor-tabs').value,false);
const legacyCompanyNav=$('company-nav');
if(legacyCompanyNav)legacyCompanyNav.onclick=event=>{
  const button=event.target.closest('[data-company-tab]');
  if(!button||button.dataset.companyTab===companyDashboard.tab)return;
  companyDashboard.tab=button.dataset.companyTab;
  if(companyDashboard.tab==='room'){
    sceneSignature='';
    loadRoom3D();
  }else{
    room3D?.stop();
  }
  renderInterior();
};
if($('company-panel'))$('company-panel').onchange=event=>updateCompanyEstimate(event,renderInterior);
$('room-company-offline').onclick=()=>toggleCompany(roomKey);
for(const id of ['floor-roster','floor-drawing'])$(id).onclick=event=>{
  const button=event.target.closest('[data-person]');
  if(!button)return;
  roomPerson=button.dataset.person;
  renderInterior();
  [...$(id).querySelectorAll('[data-person]')].find(b=>b.dataset.person===roomPerson)?.focus();
};
