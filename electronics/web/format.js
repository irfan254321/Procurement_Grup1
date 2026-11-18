const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const amount = n => new Intl.NumberFormat('id-ID',{maximumFractionDigits:2}).format(n);
const rupiah = n => 'Rp'+new Intl.NumberFormat('id-ID',{maximumFractionDigits:0}).format(n*10000);
const percent = n => (100*n).toFixed(2).replace('.',',')+'%';

function customerPriceLabel(price){
  return rupiah(price * (1+(world?.tax?.rate??0)))+(world?.tax?' termasuk PPN':'');
}
