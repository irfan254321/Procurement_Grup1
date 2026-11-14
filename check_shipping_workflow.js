// Exercise the browser handlers with a minimal DOM, including the blocked path.
const assert=require('node:assert/strict'), fs=require('node:fs'), vm=require('node:vm');
const nodes=new Map();
function element(){return {value:'10',innerHTML:'',textContent:'',children:[],dataset:{},classList:{toggle(){}},append(x){this.children.push(x)},reportValidity(){return true}}}
const get=id=>{if(!nodes.has(id))nodes.set(id,element());return nodes.get(id)};
const document={getElementById:get,createElement:element};
let agreed=false;
let vendors=[{vendor:'PT. Uji',opening_offer:120,final_offer:100,status:'accepted',SLM:1,delivery_days:5,costs:{},constraints:[],rounds:[{round:1,speaker:'buyer',action:'counter',amount:100,reason:'uji'}]}];
const fetch=async url=>({ok:true,json:async()=>url==='/api/setup'?{categories:['Pilihan'],minimums:{Pilihan:100},fixed_models:{},benchmark:{},clustering:{}}:{id:1,quantity:10,budget:100,minimum_budget:100,horizon_months:0,payment_days:30,minimum_budget_gap:1,status:agreed?'agreement':'budget_conflict',recommended:agreed?vendors[0]:null,expenditure:{reserved:agreed?100:0,remaining:0},vendors,weights:{price:.45,delivery:.2,quality:.2,risk:.15}}});
const context=vm.createContext({document,fetch,clearInterval,setInterval,console});
const html=fs.readFileSync('procurement_portal.html','utf8');
vm.runInContext(html.split('<script>')[1].split('</script>')[0],context);
(async()=>{await new Promise(r=>setImmediate(r));const e={preventDefault(){}};
 await get('form').onsubmit(e);
 for(let i=0;i<3;i++)get('next').onclick();
 assert.match(get('out').innerHTML,/Pesanan ditahan/);assert.ok(get('next').disabled||get('out').innerHTML.includes('id="next" disabled'));
 assert.doesNotMatch(get('out').innerHTML,/class="ship-truck"/);
 agreed=true;await get('form').onsubmit(e);
 for(let i=0;i<5;i++)get('next').onclick();
 assert.match(get('out').innerHTML,/Barang dalam perjalanan/);assert.match(get('out').innerHTML,/class="ship-truck"/);
 get('next').onclick();assert.match(get('out').innerHTML,/Barang tiba/);
 get('prev').onclick();assert.match(get('out').innerHTML,/Barang dalam perjalanan/);
 console.log('PASS: blocked flow stops; agreement opens packing, moving truck, delivery and back navigation');
})().catch(e=>{console.error(e);process.exitCode=1});
