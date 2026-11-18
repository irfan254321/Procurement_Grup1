const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const web = path.join(__dirname, '..', 'web');

function element(tag = '') {
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
    setAttribute() {},
    addEventListener() {},
    querySelectorAll: () => [],
    querySelector: () => null,
    focus() {},
  };
}

function fixture() {
  const vendor = 'CloudSoft Corp.';
  const roles = ['buyer', 'seller', 'stock', 'finance', 'procurement', 'deal', 'vendor'];
  const metadata = {
    scenarios: ['auto', 'healthy', 'normal', 'stock', 'cash', 'damage'],
    roles: Object.fromEntries(roles.map(role => [role, [role, 'Tugas agen']])),
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
      { name: 'Laptop', units: 4, retail: 150, vendors: [{ name: vendor }] },
      { name: 'Monitor', units: 0, retail: 90, vendors: [{ name: vendor }] },
      { name: 'Printer', units: 2, retail: 110, vendors: [{ name: vendor }] },
    ],
  };
  return { state, metadata };
}

async function checkStages() {
  const three = await import('../web/three/three.module.min.js');
  const { buildRoomStage, showroomPositions } = await import('../web/room-stage.mjs');
  const renderModule = await import('../web/room-3d.mjs');
  assert.equal(typeof renderModule.createRoom3D, 'function');
  assert.equal(showroomPositions.buyer.length, 3);
  assert.equal(showroomPositions.seller.length, 3);
  for (const role of ['buyer', 'seller', 'stock', 'finance', 'procurement', 'deal', 'vendor']) {
    const scene = new three.Scene();
    const stage = buildRoomStage(three, scene, { floor: '#ededed', color: '#72b2ad' }, role);
    assert.equal(stage.parent, scene);
    const bounds = new three.Box3().setFromObject(stage);
    const width = bounds.max.x - bounds.min.x;
    const depth = bounds.max.z - bounds.min.z;
    assert.ok(width >= 11 && width < 12, role + ' room must remain inside the stage.');
    assert.ok(depth >= 8 && depth < 9, role + ' room must remain inside the stage.');
    assert.ok(bounds.max.y > 2 && bounds.max.y < 3, role + ' room must have visible walls.');
  }
}

async function check() {
  await checkStages();
  const { state, metadata } = fixture();
  const tabs = ['world', 'profit', 'models'].map(tab => ({ ...element('button'), dataset: { tab } }));
  const nodes = new Map();
  const get = id => {
    if (!nodes.has(id)) nodes.set(id, element());
    return nodes.get(id);
  };
  let ready;
  let fetchCount=0;
  let autoResetStatus = 200;
  const actions = [];
  const document = {
    getElementById: get,
    createElement: element,
    querySelectorAll: () => tabs,
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
      return { ok: true, json: async () => route.endsWith('models') ? metadata : state };
    },
    requestAnimationFrame() {},
    performance: { now: () => 100 },
    setTimeout() {},
    clearTimeout() {},
  });

  // Read scripts in page order so this catches missing scripts and integration dependencies.
  const html = fs.readFileSync(path.join(web, 'index.html'), 'utf8');
  const scripts = [...html.matchAll(/<script defer src="\/([^"]+)"/g)].map(match => match[1]);
  assert.ok(scripts.includes('room-jobs.js'));
  for (const file of scripts) {
    if(file==='interiors.js'){
      await new Promise(resolve => setImmediate(resolve));
      assert.equal(fetchCount,0,'Startup must wait while the interior script is loading.');
    }
    vm.runInContext(fs.readFileSync(path.join(web, file), 'utf8'), context, { filename: file });
  }
  assert.equal(typeof ready,'function');
  await ready();
  assert.equal(fetchCount,2);
  assert.equal(get('error').textContent, '');
  assert.equal(get('scenario').value, 'auto');
  assert.match(get('scenario-current').textContent, /Sesi otomatis.*dana terbatas/);
  get('scenario').value = 'damage';
  get('step').onclick();
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(actions, ['/api/step/auto']);
  assert.match(get('scenario-current').textContent, /Sesi otomatis.*dana terbatas/);
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
  assert.match(get('restock-hold-lines').innerHTML, /Kekurangan dana.*Rp2[.]300[.]000/);
  assert.match(get('ledger').innerHTML, /Laba dialokasikan ke restok.*Rp3[.]000[.]000/);
  state.restock_holds = {};
  vm.runInContext('render()', context);
  assert.equal(get('restock-holds').hidden, true);

  const markers = get('markers').children;
  assert.equal(markers.length, 7);
  for (const marker of markers) {
    marker.onclick();
    assert.equal(get('map').hidden, true);
    assert.match(get('floor-drawing').innerHTML, /<svg\b/, 'Draw an SVG room when WebGL is unavailable.');
    assert.match(get('floor-roster').innerHTML, /Agent/, 'Show job labels in the roster.');
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
  console.log('Checked startup, stale-server feedback, restock holds, customer closures, showroom stock, roster and SVG fallback.');
}

check().catch(error => {
  console.error(error);
  process.exitCode = 1;
});



