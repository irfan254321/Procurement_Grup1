let world, models, vendors, carriers;
const companyId=$('company-site').dataset.company;
const companyName=companyId===bizCompanyName?null:companyId;
const companySections={'#profil':'profile','#aturan':'rules','#biaya-logistik':'logistics'};

function showCompanyPage(){
  if(world&&models)renderCompanyDashboard(companyName,companySections[location.hash]??'profile');
}

async function fetchCompanyData(path){
  const response=await fetch(path);
  if(!response.ok)throw new Error('Data perusahaan belum tersedia. Coba segarkan data.');
  return response.json();
}

async function loadCompanyPage(){
  const refresh=$('company-refresh');
  const status=$('company-page-status');
  refresh.disabled=true;
  try{
    const [snapshot,meta]=await Promise.all([fetchCompanyData('/api/world'),fetchCompanyData('/api/models')]);
    world=snapshot;
    models=meta;
    vendors=models.company_policy?.suppliers??{};
    carriers=models.company_policy?.carriers??{};
    showCompanyPage();
    status.hidden=true;
  }catch{
    status.hidden=false;
    status.textContent='Data perusahaan belum tersedia. Gunakan tombol Segarkan data untuk mencoba lagi.';
  }finally{
    refresh.disabled=false;
  }
}

$('company-refresh').onclick=loadCompanyPage;
$('company-panel').onchange=event=>updateCompanyEstimate(event,showCompanyPage);
window.addEventListener('hashchange',showCompanyPage);
loadCompanyPage();
