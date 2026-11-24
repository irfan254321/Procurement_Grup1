const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const web = path.join(__dirname, '..', '..', 'web');

function element(tag = '') {
  const attributes = new Map();
  return {
    tagName: tag.toUpperCase(),
    style: {},
    dataset: {},
    children: [],
    classList: { toggle() {}, add() {}, remove() {}, contains() { return false; } },
    innerHTML: '',
    textContent: '',
    value: '5000',
    getContext: kind => kind === '2d' ? {} : null,
    append(...children) { this.children.push(...children); },
    appendChild(child) { this.append(child); },
    replaceChildren(...children) { this.children = children; },
    insertAdjacentHTML(_, markup) { this.innerHTML += markup; },
    setAttribute(name, value) { attributes.set(name, String(value)); },
    getAttribute(name) { return attributes.get(name) ?? null; },
    addEventListener() {},
    querySelectorAll: () => [],
    querySelector: () => null,
    focus() {},
  };
}

function fixture() {
  const vendor = 'CloudSoft Corp.';
  const secondVendor = 'TechMart Inc.';
  const roles = ['buyer', 'seller', 'stock', 'finance', 'procurement', 'deal', 'vendor'];
  const metadata = {
    scenarios: ['auto', 'healthy', 'normal', 'stock', 'cash', 'damage'],
    roles: Object.fromEntries(roles.map(role => [role, [role, 'Tugas agen']])),
    company_policy: {
      restock_threshold: 3,
      supplier_replenish_ticks: 24,
      negotiation_rounds: 3,
      offer_opening_multiplier: 1.1,
      offer_floor_multiplier: .9,
      min_markup: .15,
      carriers: {
        JNE: { description: 'Layanan kargo JNE', source_url: 'https://www.jne.co.id/jtr-id', capacity: 8 },
        'J&T Cargo': { description: 'Layanan kargo J&T Cargo', capacity: 12 },
        'Pos Logistik Indonesia': { description: 'Layanan Pos Logistik Indonesia', capacity: 16 },
      },
      suppliers: {
        [vendor]: { services: [
          { name: 'Reguler', distance: 15, path: [vendor, 'Hub Utara', 'JNE', 'Gudang BIZ'], carrier: 'JNE', capacity: 8, mode: 'Darat', fixed_rate: .018, unit_rate: .004 },
          { name: 'Ekspres', distance: 17, path: [vendor, 'Hub Selatan', 'J&T Cargo', 'Gudang BIZ'], carrier: 'J&T Cargo', capacity: 12, mode: 'Darat', fixed_rate: .03468, unit_rate: .0068 },
        ] },
        [secondVendor]: { services: [
          { name: 'Reguler', distance: 18, path: [secondVendor, 'Hub Utara', 'JNE', 'Gudang BIZ'], carrier: 'JNE', capacity: 8, mode: 'Darat', fixed_rate: .02, unit_rate: .004 },
        ] },
      },
    },
    benchmark: {
      agents: Object.fromEntries(roles.map(role => [role, {
        main: 'Model uji',
        candidates: {},
        selected: [],
        baseline: .5,
      }])),
    },
  };
  const order = id => ({ id, quantity: 2, product: 'Laptop', budget: 500, buy: true });
  const state = {
    tick: 30,
    mode: 'auto',
    opening: 'cash',
    scene: 'seller',
    phase: 'seller',
    case: order(21),
    history: [],
    queue: [order(22), { ...order(23), restocked: true }],
    waiting: [order(8), order(11), order(12)],
    customer_results: [{ id: 8, product: 'Laptop', status: 'Stok tidak cukup' }],
    products: [
      { name: 'Laptop', units: 4, retail: 150, vendors: [{ name: vendor, price: 100 }, { name: secondVendor, price: 110 }] },
      { name: 'Monitor', units: 0, retail: 90, vendors: [{ name: vendor, price: 60 }] },
      { name: 'Printer', units: 2, retail: 110, vendors: [{ name: vendor, price: 80 }] },
    ],
  };
  return { state, metadata };
}

async function checkStages() {
  const three = await import('../../web/three/three.module.min.js');
  const {districtBounds,fitDistrictCamera,deliveryPath,shipmentMotion,shipmentPose}=await import('../../web/district-3d.mjs');
  for(const aspect of [.6,1,16/9,2.5]){
    const camera=new three.OrthographicCamera(-1,1,1,-1,.2,100);
    fitDistrictCamera(camera,aspect);
    assert.ok(Math.abs((camera.right-camera.left)/(camera.top-camera.bottom)-aspect)<1e-9);
    for(const x of [districtBounds.min.x,districtBounds.max.x])for(const y of [districtBounds.min.y,districtBounds.max.y])for(const z of [districtBounds.min.z,districtBounds.max.z]){
      const point=new three.Vector3(x,y,z).project(camera);
      assert.ok(Math.abs(point.x)<.94&&Math.abs(point.y)<.94,'The complete district must fit at aspect '+aspect);
      assert.ok(point.z>-1&&point.z<1,'Tower and lots must remain inside camera clipping planes.');
    }
  }
  const route=deliveryPath({x:16.2,y:6.6});
  assert.equal(route.length,4);
  assert.equal(route[1].z,4.7);
  assert.equal(route[2].z,4.7);
  assert.equal(route.at(-1).x,5.25);
  assert.equal(route.at(-1).z,3.22);

  const supplier = { x:16.2, y:6.6 };
  const carrier = { name:'JNE', x:8.2, y:13.2 };
  const motion = shipmentMotion(supplier, ['CloudSoft Corp.', 'Hub Selatan', carrier.name, 'Gudang BIZ'], carrier);
  const departure = shipmentPose(motion, 0);
  const pickup = shipmentPose(motion, 1250);
  const loading = shipmentPose(motion, 1600);
  const delivery = shipmentPose(motion, 1970);
  const arrival = shipmentPose(motion, 4450);
  assert.equal(departure.phase, 'approach');
  assert.equal(departure.position.x, carrier.x+.58);
  assert.ok(departure.position.z >= carrier.y && departure.position.z <= carrier.y+3);
  assert.equal(pickup.phase, 'pickup');
  assert.equal(pickup.position.x, supplier.x+.58);
  assert.ok(Math.abs(pickup.position.z-(supplier.y+.43)) < 1.1, 'Loading should happen at the supplier bay.');
  assert.equal(loading.phase, 'pickup');
  assert.ok(loading.position.equals(pickup.position));
  assert.ok(loading.load > 0 && loading.load < 1);
  assert.equal(delivery.phase, 'delivery');
  assert.ok(delivery.position.equals(pickup.position));
  assert.ok(motion.delivery.points.some(point => point.equals(departure.position)), 'The delivery leg should revisit the carrier terminal.');
  assert.equal(arrival.phase, 'arrived');
  assert.ok(arrival.position.equals(route.at(-1)), 'Carrier deliveries and direct deliveries end at Gudang BIZ.');
  const { buildRoomStage, roomSeats, showroomPositions } = await import('../../web/room-stage.mjs');
  const { createCharacter }=await import('../../web/character-3d.mjs');
  const renderModule = await import('../../web/room-3d.mjs');
  assert.equal(typeof renderModule.createRoom3D, 'function');
  const {planRoomPresence,sampleRoomPresence,roomEntrance}=renderModule;
  for(const role of ['vendor','carrier']){
    for(const home of [[3.02,3.78],[7.5,5.6]]){
      const outgoing=planRoomPresence(home,roomEntrance,1000,180);
      assert.deepEqual(sampleRoomPresence(outgoing,1000).position,home);
      const halfway=sampleRoomPresence(outgoing,1180+outgoing.total/.007);
      assert.equal(halfway.moving,true);
      assert.equal(halfway.done,false);
      const finished=sampleRoomPresence(outgoing,1180+outgoing.total/.0035);
      assert.deepEqual(finished.position,roomEntrance);
      assert.equal(finished.done,true);
      assert.deepEqual(sampleRoomPresence(outgoing,1000,true).position,roomEntrance);
      const incoming=planRoomPresence(roomEntrance,home,5000);
      assert.deepEqual(sampleRoomPresence(incoming,5000).position,roomEntrance);
      assert.deepEqual(sampleRoomPresence(incoming,15000).position,home);
      const reversed=planRoomPresence(halfway.position,home,2500);
      assert.deepEqual(sampleRoomPresence(reversed,2500).position,halfway.position,
        role+' reverses a status change from its current position.');
    }
  }

  assert.equal(showroomPositions.buyer.length, 3);
  assert.equal(showroomPositions.seller.length, 3);
  for (const role of ['buyer', 'seller', 'stock', 'finance', 'procurement', 'deal', 'vendor', 'carrier']) {
    assert.ok(roomSeats[role]['staff-0'], role + ' must have an occupied workstation');
    const scene = new three.Scene();
    const stage = buildRoomStage(three, scene, { floor: '#ededed', color: '#72b2ad' }, role);
    assert.equal(stage.parent, scene);
    const tasks={
      buyer:[[7.9,2.4],[6.6,4.2],[1.4,3.9],[8.75,3.9]],
      seller:[[3.1,4.4],[7.1,5.3],[4.9,2.6]],
      stock:[[3.5,4.4],[9.2,6.3],[5.4,2.7]],
      vendor:[[7.5,5.6],[5.5,4.5],[9.6,6.7]],
      carrier:[[7.5,5.6],[9.3,6.2]],
    };
    const destinations=[roomEntrance,...Object.values(roomSeats[role]).map(seat=>[seat.x,seat.z]),...(tasks[role]??[])];
    const footprints=stage.userData.walkObstacles;
    assert.ok(footprints.length>0,role+' must register its physical furniture.');
    for(const from of destinations)for(const to of destinations){
      const motion=planRoomPresence(from,to,0,0,footprints);
      assert.ok(motion,role+' must find a route to its workstations and entrance.');
      const start=motion.points[0],end=motion.points.at(-1);
      const contains=(point,box)=>point[0]>box.minX&&point[0]<box.maxX&&point[1]>box.minZ&&point[1]<box.maxZ;
      for(let segment=1;segment<motion.points.length;segment++){
        const a=motion.points[segment-1],b=motion.points[segment];
        const steps=Math.max(1,Math.ceil(Math.hypot(b[0]-a[0],b[1]-a[1])/.025));
        for(let index=0;index<=steps;index++){
          const t=index/steps,point=[a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t];
          for(const box of footprints){
            // Only the worker's departure/arrival chair is used as a docking point.
            if(box.kind==='chair'&&(contains(start,box)||contains(end,box)))continue;
            const clearance=renderModule.roomWalkClearance-1e-8;
            assert.ok(!contains(point,{minX:box.minX-clearance,maxX:box.maxX+clearance,
              minZ:box.minZ-clearance,maxZ:box.maxZ+clearance}),
              role+' route crosses a '+box.kind+' footprint.');
          }
        }
      }
    }

    const bounds = new three.Box3().setFromObject(stage);
    const width = bounds.max.x - bounds.min.x;
    const depth = bounds.max.z - bounds.min.z;
    assert.ok(width >= 11 && width < 12, role + ' room must remain inside the stage.');
    assert.ok(depth >= 8 && depth < 9, role + ' room must remain inside the stage.');
    assert.ok(bounds.max.y > 2 && bounds.max.y < 3, role + ' room must have visible walls.');
    if (role === 'seller') {
      const laptop = stage.getObjectByName('Laptop');
      stage.userData.setStock([{ name: 'Laptop', units: 0 }]);
      assert.equal(laptop.visible, false, 'A sold-out item must disappear from its 3D display.');
      stage.userData.setStock([{ name: 'Laptop', units: 2 }]);
      assert.equal(laptop.visible, true, 'A restocked item must return to its 3D display.');
    }
    if (role === 'stock') {
      const cartons = stage.getObjectByName('Kardus persediaan');
      stage.userData.setStock([{ name: 'Laptop', units: 3 }, { name: 'Printer', units: 2 }]);
      assert.equal(cartons.count, 5, 'Rack cartons must reflect actual combined stock.');
      stage.userData.setStock([]);
      assert.equal(cartons.count, 0, 'Empty warehouse shelves must not display inventory.');
    }
  }
  const worker = createCharacter({role:'finance',gender:'female',variant:1,briefcase:false});
  assert.equal(worker.root.userData.hairStyle,'bun');
  worker.animate('type',1,{seated:true,reducedMotion:true});
  assert.ok(worker.pelvis.position.y<.6);
  assert.ok(worker.rig.leftLeg.hip.rotation.x<-1);
  assert.ok(worker.rig.leftLeg.knee.rotation.x>1);
  worker.animate('walk',2,{reducedMotion:true});
  assert.ok(worker.pelvis.position.y>.8);
  worker.dispose();
}

async function checkCompanyStatus() {
  const script = fs.readFileSync(path.join(web, 'company-status.js'), 'utf8');
  for (const initiallyOffline of [false, true]) {
    let online = !initiallyOffline, reloads = 0, unavailable = false;
    const timers = new Map(), documentEvents = {}, windowEvents = {};
    let timerId = 0;
    const button = { disabled: false, addEventListener(_, listener) { this.click = listener; } };
    const message = { textContent: '' }, checkedAt = { textContent: '' };
    const document = {
      body: { dataset: { companyPath: '/cloudsoft/', companyOffline: String(initiallyOffline) } },
      hidden: false,
      getElementById: id => id === 'company-status-check' ? button : id === 'company-status-time' ? checkedAt : message,
      addEventListener: (name, listener) => { documentEvents[name] = listener; },
    };
    const routes = [];
    const context = vm.createContext({
      document, AbortSignal,
      window: { addEventListener: (name, listener) => { windowEvents[name] = listener; } },
      location: { reload() { reloads++; } },
      fetch: async route => {
        routes.push(route);
        if (unavailable) throw new Error('Server unavailable');
        return { ok: true, json: async () => ({ online, day: 593 }) };
      },
      setTimeout: callback => { timers.set(++timerId, callback); return timerId; },
      clearTimeout: id => timers.delete(id),
    });
    vm.runInContext(script, context);
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(reloads, 0);
    assert.equal(routes[0], '/api/companies/cloudsoft/status');
    assert.equal(timers.size, 1);
    if (initiallyOffline) {
      assert.match(message.textContent, /masih offline/);
      assert.match(checkedAt.textContent, /Diperiksa pukul.*593/);
    }

    unavailable = true;
    await button.click();
    assert.equal(reloads, 0, 'Connection failure must not reopen a closed company.');
    assert.match(message.textContent, /belum dapat diperiksa/);
    assert.equal(timers.size, 1);
    unavailable = false;

    document.hidden = true;
    documentEvents.visibilitychange();
    assert.equal(timers.size, 0);
    const count = routes.length;
    await button.click();
    assert.equal(routes.length, count);
    document.hidden = false;
    documentEvents.visibilitychange();
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(timers.size, 1);

    online = !online;
    await button.click();
    assert.equal(reloads, 1, 'Closing and reopening must each refresh the company site.');
    assert.equal(timers.size, 0);
    windowEvents.pagehide();
    await button.click();
    assert.equal(reloads, 1);
  }
}

async function check() {
  await checkCompanyStatus();
  await checkStages();
  const { state, metadata } = fixture();
  const tabs = ['world', 'models', 'control-tower'].map(tab => ({ ...element('button'), dataset: { tab } }));
  const nodes = new Map();
  const get = id => {
    if (!nodes.has(id)) nodes.set(id, element());
    return nodes.get(id);
  };
  const companyTabs = ['room', 'profile', 'rules', 'logistics'].map(tab => ({
    ...element('button'), dataset: { companyTab: tab },
  }));
  get('company-nav').querySelectorAll = () => companyTabs;
  get('control-tower').hidden = true;
  let ready;
  let fetchCount=0;
  let autoResetStatus = 200;
  const actions = [];
  const timerDelays = [];
  const document = {
    getElementById: get,
    createElement: element,
    querySelectorAll: selector => selector === '.tab' ? tabs : [],
    addEventListener(type,listener) { if(type==='DOMContentLoaded')ready=listener; },
  };
  const context = vm.createContext({
    document,
    window: { scrollTo() {}, addEventListener() {} },
    confirm: () => true,
    fetch: async (route, options) => {
      fetchCount++;
      if (options?.method === 'POST') actions.push(route);
      if (route === '/api/reset/auto' && autoResetStatus === 404) {
        return { ok: false, status: 404, json: async () => ({ error: 'Aksi tidak tersedia.' }) };
      }
      if (route.startsWith('/api/memory/'))return {ok:true,json:async()=>({memory:[]})};
      return { ok: true, json: async () => route.endsWith('models') ? metadata : state };
    },
    requestAnimationFrame() {},
    performance: { now: () => 100 },
    setTimeout(_, delay) { timerDelays.push(delay); },
    clearTimeout() {},
  });

  // Read scripts in page order so this catches missing scripts and integration dependencies.
  const html = fs.readFileSync(path.join(web, 'index.html'), 'utf8');
  assert.doesNotMatch(html, /data-company-tab=/, 'Operational tabs belong in the company portal.');
  assert.match(html, /data-tab="control-tower"/);
  const scripts = [...html.matchAll(/<script defer src="\/([^"]+)"/g)].map(match => match[1]);
  assert.ok(scripts.includes('room-jobs.js'));
  assert.ok(scripts.indexOf('company-dashboard.js') >= 0 && scripts.indexOf('company-dashboard.js') < scripts.indexOf('interiors.js'));
  for (const file of scripts) {
    if(file==='interiors.js'){
      await new Promise(resolve => setImmediate(resolve));
      assert.equal(fetchCount,0,'Startup must wait while the interior script is loading.');
    }
    vm.runInContext(fs.readFileSync(path.join(web, file), 'utf8'), context, { filename: file });
  }
  assert.equal(typeof ready,'function');
  await ready();
  assert.equal(fetchCount,3);
  assert.equal(get('error').textContent, '');
  assert.equal(get('scenario').value, 'auto');
  assert.match(get('scenario-current').textContent, /Sesi otomatis.*dana terbatas/);
  vm.runInContext("selected='Pemasok lama'; render();",context);
  assert.match(get('inspector').innerHTML, /Gudang/);
  get('scenario').value = 'damage';
  get('step').onclick();
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(actions, ['/api/step/auto']);
  assert.match(get('scenario-current').textContent, /Sesi otomatis.*dana terbatas/);
  vm.runInContext("selected='Pemasok lama'; render();",context);
  assert.match(get('inspector').innerHTML, /Gudang/);
  await get('reset').onclick();
  assert.deepEqual(actions, ['/api/step/auto', '/api/reset/damage']);
  const supportedScenarios = metadata.scenarios;
  metadata.scenarios = supportedScenarios.filter(scenario => scenario !== 'auto');
  get('scenario').value = 'auto';
  await get('reset').onclick();
  assert.equal(actions.length, 2, 'An old server must not receive an unsupported automatic reset.');
  assert.match(get('error').textContent, /belum mendukung mode otomatis.*Ctrl\+C/);
  delete metadata.scenarios;
  autoResetStatus = 404;
  await get('reset').onclick();
  assert.equal(actions.at(-1), '/api/reset/auto');
  assert.match(get('error').textContent, /belum mendukung mode otomatis.*Ctrl\+C/);
  autoResetStatus = 200;
  await get('reset').onclick();
  assert.equal(actions.at(-1), '/api/reset/auto');
  assert.equal(get('error').textContent, '');
  metadata.scenarios = supportedScenarios;
  get('scenario').value = 'stock';
  await get('reset').onclick();
  assert.equal(actions.at(-1), '/api/reset/stock');
  assert.equal(get('error').textContent, '');

  assert.match(get('customers').innerHTML, /Pelanggan 8.*Stok tidak cukup/);
  assert.doesNotMatch(get('customers').innerHTML, /Menunggu stok|Pelanggan (11|12|23)/);

  state.restock_holds = { Laptop: { quantity: 6, required: 940, available: 710, shortfall: 230 } };
  state.reinvested = 300;
  vm.runInContext('render()', context);
  assert.equal(get('restock-holds').hidden, false);
  assert.match(get('restock-hold-lines').innerHTML, /Laptop.*6 unit/);
  assert.match(get('restock-hold-lines').innerHTML, /Menunggu dana pengadaan/);
  assert.doesNotMatch(get('restock-hold-lines').innerHTML, /Rp/);
  state.restock_holds = {};
  vm.runInContext('render()', context);
  assert.equal(get('restock-holds').hidden, true);

  state.day=4;
  state.suppliers={ 'CloudSoft Corp.': {
    stock:{Laptop:5,Monitor:8,Printer:3},capacity:10,capacity_remaining:2,lead_days:3,
    late_probability:.28,source_vendor:'Acme <Healthcare>',domain_transfer:true,
  }};
  state.case.orders=[{id:'PO-1',vendor:'CloudSoft Corp.',quantity:2,cost:200,freight:5,invoice:227.55,
    status:'shipping',route:{name:'Jalur Utama',mode:'Darat',path:['CloudSoft Corp.','Hub Utara','Gudang BIZ']},arrival_day:7}];
  vm.runInContext('render()',context);
  assert.equal(get('supplier-section').hidden,false);
  assert.match(get('supplier-day').textContent,/Hari simulasi 4/);
  assert.match(get('supplier-list').innerHTML,/Kapasitas tersedia.*2 unit/);
  assert.match(get('supplier-list').innerHTML,/Laptop · 5 unit/);
  assert.match(get('supplier-list').innerHTML,/Acme &lt;Healthcare&gt;/);
  assert.match(get('supplier-context').textContent,/belum .*divalidasi.*elektronik/);
  assert.match(get('supply-orders').innerHTML,/PO-1.*Dikirim/);
  assert.match(get('supply-orders').innerHTML,/Ongkir.*Rp50[.]000/);
  assert.match(get('supply-orders').innerHTML,/Jalur Utama/);
  delete state.case.orders;

  const markers = get('markers').children;
  assert.equal(markers.length, 11);
  assert.deepEqual(markers.filter(marker=>marker.className.includes('carrier-marker')).map(marker=>marker.dataset.role),
    ['JNE','J&T Cargo','Pos Logistik Indonesia']);
  for (const marker of markers) {
    marker.onclick();
    assert.equal(get('map').hidden, true);
    assert.match(get('floor-drawing').innerHTML, /<svg\b/, 'Draw an SVG room when WebGL is unavailable.');
    assert.match(get('floor-roster').innerHTML, /Agent/, 'Show agent labels in the roster.');
  }

  markers[0].onclick();
  const lobby = get('floor-drawing').innerHTML;
  assert.equal(get('floor-showroom').hidden,false);
  for(const name of ['Laptop','Monitor','Printer'])assert.match(get('floor-showroom').innerHTML,new RegExp(name));
  assert.match(get('floor-showroom').innerHTML,/Monitor.*Stok habis/);
  assert.match(get('floor-showroom').innerHTML,/Rp1[.]500[.]000/);
  assert.match(lobby, /customer-22"/);
  assert.doesNotMatch(lobby, /customer-(8|11|12|21|23)"/);
  assert.doesNotMatch(get('floor-facts').innerHTML, /Menunggu stok/);

  markers[1].onclick();
  const shop = get('floor-drawing').innerHTML;
  assert.equal(get('floor-showroom').hidden,false);
  state.products[1].units=5;
  vm.runInContext('renderInterior()',context);
  assert.match(get('floor-showroom').innerHTML,/Monitor.*5 unit tersedia/);
  assert.match(shop, /customer-21"/);
  assert.doesNotMatch(shop, /customer-(8|23)"/);

  markers[2].onclick();
  assert.equal(get('floor-showroom').hidden,true);
  assert.match(get('floor-roster').innerHTML, /Agent[^<]*(?:Gudang|Penerimaan)/);
  assert.match(get('floor-drawing').innerHTML, /Agent[^<]*(?:Gudang|Penerimaan)/);
  assert.doesNotMatch(get('floor-roster').innerHTML, /\b(?:Raka|Dewi|Fajar)\b/);
  state.tick++;
  state.history = [{
    tick: state.tick,
    role: 'stock',
    title: 'Barang diterima',
    shipment: 'delivered',
    detail: 'Laptop bertambah 4 unit.',
  }];
  vm.runInContext('renderInterior()', context);
  assert.match(get('floor-roster').innerHTML, /Menerima dan memindai kardus/);
  assert.match(get('floor-drawing').innerHTML, /Membawa kardus ke rak gudang/);
  get('floor-replay').onclick();
  assert.match(get('floor-drawing').innerHTML, /floor-arm/);

  get('floor-back').onclick();
  assert.equal(get('map').hidden, false);

  const cases = [
    ['stock', { title: 'Barang diterima', shipment: 'delivered' }, 'carry'],
    ['seller', { title: 'Penjualan berhasil' }, 'scan'],
    ['seller', { title: 'Stok tidak cukup' }, 'talk'],
    ['procurement', { title: 'Permintaan penawaran' }, 'mail'],
    ['finance', { title: 'Barang diterima', shipment: 'delivered' }, 'stamp'],
    ['deal', { meeting: { event: { speaker: 'vendor' } } }, 'talk'],
    ['vendor', { title: 'Barang dalam perjalanan', shipment: 'shipping' }, 'carry'],
  ];
  for (const [role, event, kind] of cases) {
    context.event = event;
    const jobs = vm.runInContext('roomJobs(' + JSON.stringify(role) + ', event, true)', context);
    assert.ok(Object.values(jobs).some(job => job.kind === kind && job.label), role + ' should show a ' + kind + ' task.');
    const standby = vm.runInContext('roomJobs(' + JSON.stringify(role) + ', event, false)', context);
    assert.ok(Object.values(standby).every(job => job.kind === 'idle'), role + ' must not show stale transaction motions.');
  }

  const companyMarker = key => markers.find(marker => marker.dataset.role === key);
  const selectAgent = id => get('floor-roster').onclick({target:{closest:()=>({dataset:{person:id}})}});
  const selectCompanyTab = key => {
    const button = companyTabs.find(tab => tab.dataset.companyTab === key);
    get('company-nav').onclick({ target: { closest: () => button } });
    assert.equal(button.getAttribute('aria-pressed'), 'true');
    assert.equal(get('company-room').hidden, key !== 'room');
    assert.equal(get('company-panel').hidden, key === 'room');
  };
  const panel = get('company-panel');
  companyMarker('CloudSoft Corp.').onclick();
  assert.equal(get('company-name').textContent, 'CloudSoft Corp.');
  assert.match(get('floor-person').innerHTML, /Tugas di CloudSoft Corp\./);
  assert.match(get('floor-person').innerHTML, /Negosiasikan harga satuan/);
  selectAgent('staff-1');
  assert.match(get('floor-person').innerHTML, /Agent Pengiriman Vendor/);
  assert.match(get('floor-person').innerHTML, /Belum ada kiriman tercatat/);
  selectCompanyTab('profile');
  assert.match(get('company-type').textContent, /pemasok/i);
  assert.match(panel.innerHTML, /Laptop/);
  assert.match(panel.innerHTML, /Monitor/);
  assert.match(panel.innerHTML, /Printer/);
  selectCompanyTab('rules');
  assert.match(panel.innerHTML, /24\s+giliran/i);
  assert.match(panel.innerHTML, /3\s+putaran/i);
  selectCompanyTab('logistics');
  assert.match(panel.innerHTML, /Reguler/);
  assert.match(panel.innerHTML, /Ekspres/);
  assert.match(panel.innerHTML, /Belum ada.*(?:kiriman|pesanan)/i);
  assert.match(panel.innerHTML, /Rp22[.]000/);
  const httpCallsBeforeEstimate = fetchCount;
  panel.onchange({ target: { id: 'company-estimate-quantity', value: '7' } });
  assert.match(panel.innerHTML, /Rp46[.]000/);
  panel.onchange({ target: { id: 'company-estimate-product', value: 'Monitor' } });
  assert.match(panel.innerHTML, /Rp27[.]600/);
  panel.onchange({ target: { id: 'company-estimate-quantity', value: '90' } });
  assert.match(panel.innerHTML, /company-estimate-quantity[^>]*value="40"/);
  assert.match(panel.innerHTML, /Maks\. 8 unit/);
  assert.match(panel.innerHTML, /Maks\. 12 unit/);
  assert.equal(fetchCount, httpCallsBeforeEstimate, 'Estimating freight should not send a transaction.');

  const purchaseOrder = (id, vendor, status, freight, carrier='JNE') => ({
    id, vendor, status, freight, product:'Laptop', quantity:2, unit_cost:100, cost:200+freight,
    goods_cost:200, invoice:227.55, route:{name:'Reguler',carrier,path:[vendor,'Hub Utara',carrier,'Gudang BIZ']},
    arrival_day:7, deadline_day:8,
  });
  const paid = purchaseOrder('CS-PAID', 'CloudSoft Corp.', 'paid', 10, 'J&T Cargo');
  const shipping = purchaseOrder('CS-OPEN', 'CloudSoft Corp.', 'shipping', 5);
  const other = purchaseOrder('TM-PAID', 'TechMart Inc.', 'paid', 90);
  state.purchase_orders = [{ product:'Laptop', orders:[paid, other] }];
  state.last_purchase = { product:'Laptop', orders:[{ ...paid }, shipping] };
  state.case.orders = [purchaseOrder(undefined, 'CloudSoft Corp.', 'proposed', 42)];
  vm.runInContext('renderInterior()', context);
  assert.equal((panel.innerHTML.match(/data-company-order="CS-PAID"/g) ?? []).length, 1,
    'A settled order retained in purchase history and the latest batch should be counted once.');
  assert.match(panel.innerHTML, /data-company-order="CS-OPEN"/);
  assert.doesNotMatch(panel.innerHTML, /TM-PAID|Rp420[.]000/);
  assert.match(panel.innerHTML, /id="company-paid-freight"[^>]*>\s*Rp100[.]000/);
  assert.match(panel.innerHTML, /id="company-open-freight"[^>]*>\s*Rp50[.]000/);

  state.tick++;
  state.scene='vendor';
  state.history=[{tick:state.tick, role:'vendor', shipment:'shipping', vendor:shipping.vendor,
    title:'Barang dalam perjalanan', detail:'Kiriman dalam perjalanan.', shipments:[shipping]}];
  vm.runInContext('render(); playing=true; schedule(); playing=false;', context);
  assert.match(get('live-scene').innerHTML, /JNE/);
  assert.match(get('live-scene').innerHTML, /CloudSoft Corp\./);
  assert.equal(timerDelays.at(-1), 5200, 'Autoplay should allow time for the carrier pickup and delivery animation.');

  selectCompanyTab('room');
  selectAgent('staff-1');
  assert.match(get('floor-person').innerHTML, /CS-OPEN.*JNE/);
  assert.doesNotMatch(get('floor-person').innerHTML, /TM-PAID/);

  companyMarker('JNE').onclick();
  assert.equal(get('company-name').textContent, 'JNE');
  assert.match(get('floor-title').textContent, /Terminal logistik/i);
  assert.match(get('floor-roster').innerHTML, /Agent Dispatch.*Agent Angkut/);
  assert.match(get('floor-person').innerHTML, /Periksa jumlah muatan/);
  selectAgent('staff-1');
  assert.match(get('floor-person').innerHTML, /Berhenti untuk mengambil dan memuat barang/);
  assert.match(get('floor-person').innerHTML, /CS-OPEN.*CloudSoft Corp\./);
  assert.doesNotMatch(get('floor-person').innerHTML, /CS-PAID/);
  selectCompanyTab('profile');
  assert.match(get('company-type').textContent, /perusahaan logistik/i);
  assert.match(panel.innerHTML, /https:\/\/www\.jne\.co\.id\/jtr-id/);
  selectCompanyTab('rules');
  assert.match(panel.innerHTML, /8\s+unit per kiriman/);
  assert.match(panel.innerHTML, /terminal pengangkut/);
  selectCompanyTab('logistics');
  assert.match(panel.innerHTML, /data-company-order="CS-OPEN"/);
  assert.match(panel.innerHTML, /data-company-order="TM-PAID"/);
  assert.doesNotMatch(panel.innerHTML, /CS-PAID|Ekspres/);
  assert.match(panel.innerHTML, /id="company-paid-freight"[^>]*>\s*Rp900[.]000/);
  assert.match(panel.innerHTML, /id="company-open-freight"[^>]*>\s*Rp50[.]000/);
  panel.onchange({ target: { id:'company-estimate-vendor', value:'TechMart Inc.' } });
  assert.match(panel.innerHTML, /Rp26[.]400/);

  companyMarker('J&T Cargo').onclick();
  selectCompanyTab('logistics');
  assert.match(panel.innerHTML, /data-company-order="CS-PAID"/);
  assert.doesNotMatch(panel.innerHTML, /CS-OPEN|TM-PAID/);
  assert.match(panel.innerHTML, /id="company-paid-freight"[^>]*>\s*Rp100[.]000/);

  companyMarker('TechMart Inc.').onclick();
  assert.equal(get('company-name').textContent, 'TechMart Inc.');
  assert.match(get('floor-person').innerHTML, /Tugas di TechMart Inc\./);
  selectAgent('staff-1');
  assert.match(get('floor-person').innerHTML, /TM-PAID/);
  assert.doesNotMatch(get('floor-person').innerHTML, /CS-OPEN/);
  assert.equal(panel.hidden, true, 'Changing companies should return to the interior view.');
  selectCompanyTab('profile');
  assert.match(panel.innerHTML, /Laptop/);
  assert.doesNotMatch(panel.innerHTML, /Monitor|Printer/);
  selectCompanyTab('logistics');
  assert.match(panel.innerHTML, /data-company-order="TM-PAID"/);
  assert.doesNotMatch(panel.innerHTML, /CS-PAID|CS-OPEN/);

  companyMarker('finance').onclick();
  assert.equal(get('company-name').textContent, 'PT. Biz Indonesia Market');
  selectCompanyTab('profile');
  assert.match(get('company-type').textContent, /distributor/i);
  assert.match(panel.innerHTML, /6\s+lantai/);
  assert.match(panel.innerHTML, /2\s+perusahaan/);
  assert.match(panel.innerHTML, /Pengangkut terdaftar.*3\s+perusahaan/);
  selectCompanyTab('rules');
  assert.match(panel.innerHTML, /15\s*%/);
  selectCompanyTab('logistics');
  assert.match(panel.innerHTML, /data-company-order="TM-PAID"/);
  assert.match(panel.innerHTML, /data-company-order="CS-PAID"/);
  assert.match(panel.innerHTML, /id="company-paid-freight"[^>]*>\s*Rp1[.]000[.]000/);
  companyMarker('stock').onclick();
  assert.equal(panel.hidden, false, 'Moving between BIZ floors should preserve the selected company tab.');
  selectCompanyTab('room');
  get('floor-back').onclick();
  assert.equal(get('floor-view').hidden, true);
  assert.equal(get('map').hidden, false);


  selectCompanyTab('room');
  for(const name of [...Object.keys(metadata.company_policy.suppliers),...Object.keys(metadata.company_policy.carriers)]){
    companyMarker(name).onclick();
    state.company_availability ??= {};
    state.company_availability[name]=false;
    state.history=[{tick:state.tick,role:'vendor',vendor:name,title:'Pesanan disiapkan',detail:'Pesanan perusahaan.',
      shipments:[{vendor:'CloudSoft Corp.',quantity:1,route:{carrier:name}}]}];
    vm.runInContext('renderInterior()',context);
    assert.match(get('floor-status').textContent,/Offline/);
    assert.doesNotMatch(get('floor-drawing').innerHTML,/data-person=/,
      name+' has no people or pins in the offline SVG fallback.');
    assert.match(get('floor-roster').innerHTML,/Di luar kantor/);
    if(state.history.length)assert.equal(get('floor-replay').disabled,true);
    state.company_availability[name]=true;
    vm.runInContext('renderInterior()',context);
    assert.match(get('floor-drawing').innerHTML,/data-person="staff-0"/,
      name+' repopulates when the company comes online.');
  }

  console.log('Checked district framing, carrier pickup and delivery, company dashboards, stock, roster and SVG fallback.');
}

check().catch(error => {
  console.error(error);
  process.exitCode = 1;
});



