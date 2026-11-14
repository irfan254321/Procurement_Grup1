"""End-to-end check using temporary rules/history, never user transactions."""
import json,sqlite3,sys,tempfile,threading,urllib.request
from pathlib import Path
from http.server import ThreadingHTTPServer
from contextlib import closing
import procurement_web as web

source=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else web.ROOT
html=(web.ROOT/'procurement_portal.html').read_bytes()
policy_bytes=(source/'config/buyer_policy.json').read_bytes()
with tempfile.TemporaryDirectory() as d:
    web.ROOT=Path(d);web.MODELS=source/'runs/agent_benchmark'
    catalog=web.ROOT/'runs/bpi_offers';catalog.mkdir(parents=True)
    for f in ('catalog.json','vendor_aliases.json','completed_transactions.json'):
        (catalog/f).write_bytes((source/'runs/bpi_offers'/f).read_bytes())
    (web.ROOT/'procurement_portal.html').write_bytes(html)
    (web.ROOT/'config').mkdir()
    (web.ROOT/'config/buyer_policy.json').write_bytes(policy_bytes)
    server=ThreadingHTTPServer(('127.0.0.1',0),web.Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    prefix='http://127.0.0.1:'+str(server.server_port)
    def call(path,payload=None):
        return json.load(urllib.request.urlopen(urllib.request.Request(prefix+path,data=None if payload is None else json.dumps(payload).encode()),timeout=60))
    try:
        assert b'shippingScene' in urllib.request.urlopen(prefix).read()
        setup=call('/api/setup');assert len(setup['categories'])==10 and len(set(setup['fixed_models'].values()))==4
        assert setup['api_version']==3 and 'clustering' not in setup
        assert call('/api/models')['fixed_models']==setup['fixed_models']
        assert setup['fixed_models']['IRE']=='SVM (linear)'
        assert all('Cluster+Logistic' not in t['models'] for t in setup['benchmark'].values())
        assert call('/api/buyer-policy')==setup['buyer_policy']
        assert len(call('/api/vendor-rules')['vendors'])==5
        assert call('/api/history')==[], 'Creating vendor rules must not break an empty history'
        assert all(v>0 for v in setup['minimums'].values())
        for cat,budget in setup['minimums'].items():
            low=call('/api/estimate',{'category':cat,'budget':round(budget-.01,2)})
            assert low['status']=='budget_conflict' and low['minimum_budget']==budget
            assert len(low['vendors'])==5
        category=setup['categories'][0]; cap=setup['minimums'][category]
        funds=dict(cash=cap*3,receipts=cap*.1,payroll=cap*.3,operations=cap*.2,
                   commitments=cap*.1,reserve=cap*.2,procurement_funds=cap,
                   revenue=cap*3,period_expenses=cap*.6)
        low=call('/api/simulate',{'category':category,'budget':round(cap-.01,2),'finance':funds})
        high=call('/api/simulate',{'category':category,'budget':cap,'finance':funds,'weights':{'price':0,'delivery':0,'quality':0,'risk':100}})
        assert high['weights']['price']==.45, 'Client must not override company policy'
        assert low['status']=='budget_conflict' and low['expenditure']['reserved']==0
        assert high['status']=='agreement' and 0<high['expenditure']['reserved']<=cap
        assert any(e['action']=='counter' for v in high['vendors'] for e in v['rounds'])
        assert high['models']==setup['fixed_models'] and high['recommended']['score'] is not None
        future=call('/api/estimate',{'category':category,'budget':cap,'horizon_months':3})
        assert future['vendors'][0]['costs']['unit_cost_forecast']>high['vendors'][0]['costs']['unit_cost_forecast']
        assert high['finance']['approved'] and high['finance']['vendor']==high['recommended']['vendor']
        assert high['finance']['due_days']==high['payment_days']
        for changes,reason in [
            ({'cash':cap*.4}, 'Kas kurang'),
            ({'procurement_funds':0}, 'Dana kategori'),
            ({'revenue':0}, 'Proyeksi rugi'),
        ]:
            blocked=call('/api/simulate',{'category':category,'budget':cap,'finance':{**funds,**changes}})
            assert blocked['status']=='agreement' and not blocked['finance']['approved']
            assert blocked['expenditure']['reserved']==0 and blocked['expenditure']['due_days_after_invoice'] is None
            assert len(blocked['finance']['reasons'])==1 and reason in blocked['finance']['reasons'][0]
        assert len(call('/api/history'))==5 and len(call('/api/completed'))==30
        with closing(sqlite3.connect(web.ROOT/'data/web_procurement.sqlite3')) as db:
            assert db.execute('SELECT COUNT(*) FROM negotiation_vendor_rules').fetchone()[0]==50
        print('PASS: ten categories, fifty persisted profiles, four distinct native models, counteroffer, budget boundary, forecast, expenses, and historical invoices')
        print('Minimums:',setup['minimums']);print('Example: before',low['budget'],low['status'],'after',high['budget'],high['status'])
    finally:
        server.shutdown();server.server_close()

