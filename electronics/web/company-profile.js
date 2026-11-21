let world, models, vendors, carriers;
const companyId = document.body.dataset.company;
const companyName = companyId === bizCompanyName ? null : companyId;
const companyPath = document.body.dataset.companyPath;
const companyViews = new Map([
  ['#aturan', { tab: 'rules', title: 'Aturan operasional', description: 'Ketentuan perusahaan dalam menangani pesanan dan pengiriman di BIZ District.' }],
  ['#biaya-logistik', { tab: 'logistics', title: 'Biaya logistik', description: 'Lihat ongkir tercatat dan bandingkan estimasi berdasarkan rute, jarak, dan jumlah unit.' }],
  ['#ringkasan', { tab: 'profile', title: 'Ringkasan operasional', description: 'Lihat informasi dan data perusahaan dari kondisi simulasi saat ini.' }],
  ['#negosiasi', { tab: 'negotiations', private: true, title: 'Jadwal & negosiasi', description: 'Buka jadwal, riwayat tawar-menawar, dan penawaran pengiriman perusahaan.' }],
]);
if (companyPath === '/biz/') companyViews.set('#keuangan', {
  tab: 'finance', private: true, title: 'Keuangan BIZ',
  description: 'Laporan laba rugi, neraca, arus kas, dan pencatatan pajak PT. Biz Indonesia Market.',
});
const story = $('profil');
const storyHeading = story.querySelector('h1');
const operations = $('company-operations');
const operationTitle = $('profile-operation-title');
const status = $('company-page-status');
const refresh = $('company-refresh');
const links = document.querySelectorAll('[data-company-view]');
const profileMetrics = $('profile-metrics');
const siteTitle = document.title;
let currentView;

function renderOperations() {
  if (!currentView || currentView.private || !world || !models) return;
  $('company-context').textContent = 'Hari simulasi ' + amount(world.day ?? 0);
  renderCompanyPanel(companyName, currentView.tab);
  $('company-panel').hidden = false;
}

function renderProfileMetrics() {
  if (!profileMetrics) return;
  const carrier = carriers[companyName];
  const supplier = world.suppliers?.[companyName];
  const catalogue = companyProducts(companyName);
  const shipments = carrier ? companyOrders(companyName) : [];
  const data = carrier ? [
    ['Kapasitas per kiriman',carrier.capacity,' unit'],
    ['Kiriman tercatat',shipments.length,''],
    ['Kiriman dengan faktur terbuka',shipments.filter(order=>order.status!=='paid').length,''],
  ] : [
    ['Produk dalam katalog',catalogue.length,''],
    ['Stok tersedia',catalogue.reduce((total,item)=>total+(item.stock??0),0),' unit'],
    ['Kapasitas tersisa',supplier?.capacity_remaining??0,' unit'],
  ];
  profileMetrics.querySelector('dl').innerHTML = data.map(([label,value,unit])=>
    '<div><dt>'+esc(label)+'</dt><dd>'+esc(amount(value)+unit)+'</dd></div>').join('');
  profileMetrics.hidden = false;
}

async function fetchCompanyData(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error('Gagal memuat data perusahaan.');
  return response.json();
}

async function loadOperations() {
  if (refresh.disabled) return;
  refresh.disabled = true;
  status.hidden = !!currentView?.private;
  status.textContent = 'Memuat data perusahaan…';
  try {
    const [snapshot, metadata] = await Promise.all([
      fetchCompanyData('/api/world'),
      fetchCompanyData('/api/models'),
    ]);
    world = snapshot;
    models = metadata;
    vendors = models.company_policy?.suppliers ?? {};
    carriers = models.company_policy?.carriers ?? {};
    renderProfileMetrics();
    renderOperations();
    status.hidden = true;
  } catch {
    status.textContent = 'Data perusahaan belum tersedia. Klik Segarkan data untuk mencoba lagi.';
  } finally {
    refresh.disabled = false;
  }
}

function showCompanyView(moveFocus = false) {
  const view = companyViews.get(location.hash);
  if (view === currentView && moveFocus) return;
  currentView = view;
  story.hidden = !!view;
  operations.hidden = !view;
  const privateView=!!view?.private;
  $('company-negotiations').hidden=!privateView;
  if(privateView){
    $('company-panel').hidden=true;
    $('company-context').textContent='';
  }
  status.hidden=privateView||!!(world&&models);
  document.title = view ? view.title + ' | ' + companyId : siteTitle;
  const activeLink = view ? location.hash : '#profil';
  for (const link of links) {
    if (link.hash === activeLink) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  }
  if (view) {
    operations.dataset.section = view.tab;
    operationTitle.textContent = view.title;
    $('profile-operation-intro').textContent = view.description;
    if (privateView) loadCompanyPrivate(view.tab);
    else if (world && models) renderOperations();
    else loadOperations();
  }
  if (!moveFocus) return;
  const anchor = !view && document.getElementById(location.hash.slice(1));
  const heading = view ? operationTitle : storyHeading;
  heading?.focus({ preventScroll: true });
  if (anchor) anchor.scrollIntoView({ behavior: 'instant' });
  else window.scrollTo({ top: 0, behavior: 'instant' });
}

if (location.pathname !== companyPath) {
  const legacyDashboard = location.pathname.replace(/\/$/, '').endsWith('/dashboard');
  const hash = legacyDashboard && (!location.hash || location.hash === '#profil') ? '#ringkasan' : location.hash;
  history.replaceState(history.state, '', companyPath + location.search + hash);
}

if (storyHeading) storyHeading.tabIndex = -1;
document.querySelector('a[href="#konten"]').addEventListener('click', event => {
  if (!currentView) return;
  event.preventDefault();
  operationTitle.focus();
});
refresh.addEventListener('click',()=>currentView?.private?loadCompanyPrivate(currentView.tab):loadOperations());
$('company-panel').addEventListener('change', event => updateCompanyEstimate(event, renderOperations));
window.addEventListener('hashchange', () => showCompanyView(true));
showCompanyView();
if (profileMetrics) loadOperations();

const profileMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
if (!profileMotion.matches && 'IntersectionObserver' in window && typeof Element.prototype.animate === 'function') {
  const profileReveal = new IntersectionObserver(entries => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      profileReveal.unobserve(entry.target);
      if (profileMotion.matches || entry.target.contains(document.activeElement)) continue;
      entry.target.animate(
        [{ opacity: .55, transform: 'translateY(16px)' }, { opacity: 1, transform: 'translateY(0)' }],
        { duration: 440, easing: 'cubic-bezier(.2,.7,.3,1)' },
      );
    }
  }, { threshold: .14 });
  document.querySelectorAll('[data-profile-reveal]').forEach(section => profileReveal.observe(section));
}
