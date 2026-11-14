const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const nodes=new Map();
const el=()=>({innerHTML:'',textContent:'',value:'',children:[],dataset:{},classList:{toggle(){},add(){}},append(v){this.children.push(v)}});
const get=k=>{if(!nodes.has(k))nodes.set(k,el());return nodes.get(k)};
const r={id:1,company:'PT. Biz Indonesia Market',status:'budget_conflict',quantity:10,budget:100,minimum_budget:110,minimum_budget_gap:10,weights:{price:.45,delivery:.2,quality:.2,risk:.15},expenditure:{reserved:0},vendors:['PT. Vendor Satu','PT. Vendor Dua'].map((vendor)=>({vendor,costs:{},constraints:[],rounds:[{round:0,speaker:'vendor',action:'opening',amount:120,reason:'Harga pembuka'},{round:1,speaker:'buyer',action:'counter',amount:100,reason:'Batas anggaran'},{round:1,speaker:'vendor',action:'counter',amount:110,reason:'Margin minimum'},{round:1,speaker:'buyer',action:'reject',amount:110,reason:'Di luar anggaran'}]}))};
const html=fs.readFileSync('procurement_portal.html','utf8');
const code=html.split('<script>')[1].split('</script>')[0];
let ms,fn,cancelled;
const c=vm.createContext({document:{getElementById:get,createElement:el}, fetch:()=>new Promise(()=>{}),setTimeout:(cb,d)=>{ms=d;fn=cb;return 1},clearTimeout:()=>{cancelled=true},console});
vm.runInContext(code,c); c.fixture=r;vm.runInContext('workflow(fixture)',c);
const out=()=>get('out').innerHTML;
get('next').onclick();get('next').onclick();
assert.match(out(),/PT\. Biz Indonesia Market/);assert.match(out(),/PT\. Vendor Satu/);assert.doesNotMatch(out(),/PT\. Vendor Dua/);
get('play').onclick();assert.equal(ms,7000);fn();assert.match(out(),/Harga pembuka/);assert.doesNotMatch(out(),/Batas anggaran/);
get('play').onclick();assert.ok(cancelled);get('next').onclick();assert.match(out(),/Batas anggaran/);
get('prev').onclick();assert.match(out(),/Harga pembuka/);get('next').onclick();get('next').onclick();get('next').onclick();assert.match(out(),/Di luar anggaran/);
get('next').onclick();assert.match(out(),/PT\. Vendor Dua/);assert.doesNotMatch(out(),/PT\. Vendor Satu/);
get('pace').value='15';get('pace').onchange();get('play').onclick();assert.equal(ms,15000);
console.log('PASS: vendor-by-vendor introductions, alternating offers, backward navigation, pause and 7s/15s pacing');

c.fixture={...r,status:'agreement',recommended:{vendor:'PT. Vendor Satu',final_offer:95,delivery_days:5},payment_days:30,
 finance:{approved:false,vendor:'PT. Vendor Satu',due_days:30,reasons:['Kas kurang setelah gaji.']}};
vm.runInContext('workflow(fixture)',c);
while(!out().includes('Keputusan Agent Keuangan'))get('next').onclick();
assert.match(out(),/DITAHAN KEUANGAN/);
assert.match(out(),/Kas kurang setelah gaji/);
assert.match(out(),/id="next" disabled/);

c.fixture.finance.approved=true;
c.fixture.finance.reasons=[];
vm.runInContext('workflow(fixture)',c);
while(!out().includes('Evaluasi dan rencana pembayaran'))get('next').onclick();
get('play').onclick();fn();
assert.match(out(),/DISETUJUI KEUANGAN/);
assert.match(out(),/id="play">Putar alur/);
get('next').onclick();
assert.match(out(),/PT\. Vendor Satu menyiapkan barang/);
console.log('PASS: finance decision pauses playback, blocks shipping or releases the selected vendor');
