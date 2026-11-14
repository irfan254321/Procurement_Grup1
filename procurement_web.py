from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from functools import lru_cache
import json,sqlite3
from urllib.parse import parse_qs,urlsplit
from joblib import load
from negotiation_catalog import scenarios,rules,MODELS as FIXED_MODELS,DEFAULT
from procurement_negotiation import negotiate
from procurement_finance import evaluate_finance

ROOT=Path(__file__).resolve().parent
MODELS=ROOT/'runs/agent_benchmark'
COMPANY='PT. Biz Indonesia Market'
API_VERSION=3
@lru_cache
def model(agent,name):return load(MODELS/f'{agent}_{name.split()[0]}.joblib')
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def catalog():
    return scenarios(ROOT)
def benchmark():
    report=read(MODELS/'results.json')
    for agent,entry in report.items():
        entry['models'].pop('Cluster+Logistic',None)
        entry['recommended']=FIXED_MODELS[agent]
    return report
def buyer_policy():
    policy=read(ROOT/'config/buyer_policy.json')
    weights=policy['weights']
    if (policy['company']!=COMPANY or set(weights)!={'price','delivery','quality','risk'}
            or any(type(v) is not int or not 0<=v<=100 for v in weights.values())
            or sum(weights.values())!=100):
        raise ValueError('Aturan pembeli tidak valid: bobot harus berjumlah 100.')
    return policy
def simulate(payload,persist=True):
    if not isinstance(payload,dict):raise ValueError('Masukan harus berupa objek permintaan.')
    groups=catalog();r=read(MODELS/'results.json');choices=dict(FIXED_MODELS)
    budget=payload.get('budget',1)
    frame=groups[payload['category']].copy(); frame['month']=9;frame['weekday']=5
    profiles=rules(ROOT,payload['category'],frame)
    args={k:payload.get(k,v) for k,v in DEFAULT.items()}
    weights=buyer_policy()['weights']
    if not persist:return negotiate(profiles,budget,weights=weights,**args)
    intake=frame.iloc[[0]].copy();intake['initial_po_value']=frame.initial_po_value.median()
    predictions={a:model(a,choices[a]).predict((intake if a=='IRE' else frame)[t['features']]).reshape(-1).astype(int).tolist() for a,t in r.items()}
    for i,v in enumerate(profiles):
        v['risk']=min(1.,v['risk']+(.20 if predictions['VMI'][i]==0 else 0))
        v['concession_fraction']=.30 if predictions['DA'][i]==1 else .55
    result=negotiate(profiles,budget,weights=weights,**args)
    result.update(company=COMPANY,category=payload['category'],models=choices,
                  intake_revision=predictions['IRE'][0],rule_source='Asumsi simulasi dalam satuan nilai BPI')
    for i,v in enumerate(result['vendors']):
        v.update({'value':v['opening_offer'],'eligible':v['status']=='accepted',
          **{a:p[0 if a=='IRE' else i] for a,p in predictions.items()}})
    chosen=result['recommended']
    result['finance']=evaluate_finance(result,payload.get('finance') or {})
    authorized=chosen if result['finance']['approved'] else None
    result['expenditure']={'reserved':authorized['final_offer'] if authorized else 0,
        'remaining':round(result['budget']-(authorized['final_offer'] if authorized else 0),2),
        'due_days_after_invoice':result['payment_days'] if authorized else None}
    path=ROOT/'data/web_procurement.sqlite3';path.parent.mkdir(exist_ok=True)
    db=sqlite3.connect(path)
    with db:
        db.execute('CREATE TABLE IF NOT EXISTS requests(id INTEGER PRIMARY KEY, result TEXT)')
        result['id']=db.execute('INSERT INTO requests(result) VALUES(?)',(json.dumps(result),)).lastrowid
    db.close();return result
class Handler(BaseHTTPRequestHandler):
    def respond(self,data,status=200,mime='application/json'):
        body=data if isinstance(data,bytes) else json.dumps(data,ensure_ascii=False).encode()
        self.send_response(status);self.send_header('Content-Type',mime+'; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def do_GET(self):
        try:self.get_route()
        except (OSError,sqlite3.Error,ValueError,KeyError) as e:
            self.log_error('GET %s: %s',self.path,e)
            self.respond({'error':'Data portal belum bisa dimuat. Cek konfigurasi, database, dan artefak model pada terminal server.'},503)
    def get_route(self):
        route=urlsplit(self.path)
        if route.path=='/':return self.respond((ROOT/'procurement_portal.html').read_bytes(),mime='text/html')
        if route.path=='/api/models':
            return self.respond({'fixed_models':FIXED_MODELS,'benchmark':benchmark(),'api_version':API_VERSION})
        if route.path=='/api/buyer-policy':return self.respond(buyer_policy())
        if route.path=='/api/vendor-rules':
            groups=catalog();category=parse_qs(route.query).get('category',[next(iter(groups))])[0]
            if category not in groups:return self.respond({'error':'Kategori pengadaan tidak ditemukan.'},400)
            return self.respond({'category':category,'vendors':rules(ROOT,category,groups[category])})
        if route.path=='/api/setup':
            groups=catalog()
            policy=buyer_policy()
            minimums={k:negotiate(rules(ROOT,k,g),1,weights=policy['weights'],**DEFAULT)['minimum_budget'] for k,g in groups.items()}
            return self.respond({'api_version':API_VERSION,'categories':list(groups),'minimums':minimums,'defaults':DEFAULT,
                'buyer_policy':policy,'fixed_models':FIXED_MODELS,'benchmark':benchmark()})
        if route.path=='/api/history':
            p=ROOT/'data/web_procurement.sqlite3';rows=[]
            if p.exists():
                db=sqlite3.connect(p)
                try:
                    if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='requests'").fetchone():
                        rows=[dict(json.loads(x[1]),id=x[0]) for x in db.execute('select id,result from requests order by id desc limit 50')]
                finally:db.close()
            return self.respond(rows)
        if route.path=='/api/completed':
            names=read(ROOT/'runs/bpi_offers/vendor_aliases.json');s=read(ROOT/'runs/bpi_offers/completed_transactions.json')
            return self.respond([{'vendor':names.get(r['vendor'],'Vendor anonim'),'po':r['case_id'],'value':r['initial_po_value'],'cleared':r['cleared_at'],'days':r['actual_payment_days']} for r in s['cases'] if r['company']=='companyID_0000'][:30])
        self.respond({'error':'Halaman tidak ditemukan'},404)
    def do_POST(self):
        if self.path not in ('/api/simulate','/api/estimate'):return self.respond({'error':'Rute tidak ditemukan'},404)
        try:
            n=int(self.headers.get('Content-Length','0'))
            if not 0<n<=16384:raise ValueError('Ukuran permintaan tidak valid.')
            self.respond(simulate(json.loads(self.rfile.read(n)),persist=self.path=='/api/simulate'))
        except (ValueError,KeyError,TypeError) as e:self.respond({'error':str(e)},400)
if __name__=='__main__':
    print('Portal lokal: http://127.0.0.1:8080',flush=True)
    ThreadingHTTPServer(('127.0.0.1',8080),Handler).serve_forever()

