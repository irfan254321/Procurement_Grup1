const assert=require('node:assert/strict'), fs=require('node:fs'), vm=require('node:vm');
const html=fs.readFileSync('procurement_portal.html','utf8');
assert.doesNotMatch(html,/id="clusters"|id="weight-price"|clusters:'Clustering'/);
const code=html.split('<script>')[1].split('</script>')[0];
function boot(old){
 const nodes=new Map(),requests=[];
 function element(){
  const classes=new Set();
  return {value:'',innerHTML:'',textContent:'',children:[],dataset:{},classList:{toggle(k,on){if(on)classes.add(k);else classes.delete(k)},add(k){classes.add(k)},contains(k){return classes.has(k)}},append(x){this.children.push(x)},reportValidity(){return false}};
 }
 function get(id){if(!nodes.has(id))nodes.set(id,element());return nodes.get(id)}
 const fixed_models={IRE:'SVM (linear)',VMI:'XGBoost',DA:'Extra Trees',SLM:'CatBoost'};
 const benchmark={};
 const setup={api_version:2,categories:['Produk & Label'],minimums:{'Produk & Label':124.29},fixed_models,benchmark,buyer_policy:{company:'PT. Biz Indonesia Market',weights:{price:45,delivery:20,quality:20,risk:15},description:'Aturan tetap'}};
 const vendors=Array.from({length:5},(_,i)=>({vendor:'PT. Contoh '+i,unit_cost_now:10,labor_cost_per_unit:1,shipping_cost:2,min_margin:.1}));
 const fetch=async(url,options)=>{
  requests.push([url,options]);
  const result=url==='/api/setup'?(old?{categories:['Old · Key'],benchmark}:setup):url==='/api/models'?{fixed_models,benchmark}:url.startsWith('/api/vendor-rules?')?{category:'Produk & Label',vendors}:[];
  return {ok:true,json:async()=>result};
 };
 vm.runInContext(code,vm.createContext({document:{getElementById:get,createElement:element},fetch,clearInterval,setInterval,console}));
 return {get,requests,go:id=>get('nav').children.find(x=>x.dataset.id===id).onclick()};
}
(async()=>{
 const fresh=boot(false);await new Promise(r=>setImmediate(r));
 assert.match(fresh.get('category').innerHTML,/Produk &amp; Label/);assert.equal(fresh.get('budget').value,'124.29');assert.equal(fresh.get('run').disabled,false);
 await fresh.go('buyer');assert.match(fresh.get('buyer').innerHTML,/PT\. Biz Indonesia Market/);assert.match(fresh.get('buyer').innerHTML,/45%/);
 fresh.get('budget').value='';await fresh.go('rules');assert.match(fresh.get('rules-results').innerHTML,/5 profil vendor/);assert.match(fresh.get('rules-results').innerHTML,/PT\. Contoh 4/);
 assert.ok(fresh.requests.some(([u,o])=>u==='/api/vendor-rules?category=Produk%20%26%20Label'&&o.method===undefined));
 assert.ok(!fresh.requests.some(([u])=>u==='/api/estimate'));
 await fresh.go('benchmark');assert.match(fresh.get('benchmark').innerHTML,/IRE · SVM \(linear\)/);assert.match(fresh.get('benchmark').innerHTML,/SLM · CatBoost/);
 const old=boot(true);await new Promise(r=>setImmediate(r));
 assert.match(old.get('setup-status').innerHTML,/API server versi lama/);assert.equal(old.get('run').disabled,true);
 await old.go('rules');assert.match(old.get('rules').innerHTML,/Ctrl\+C/);
 await old.go('benchmark');assert.match(old.get('benchmark').innerHTML,/VMI · XGBoost/);assert.ok(old.requests.some(([u])=>u==='/api/models'));
 console.log('PASS: kategori dan minimum termuat, bobot pindah, lima vendor tanpa anggaran, model mandiri, API lama ditangani');
})().catch(e=>{console.error(e);process.exitCode=1});
