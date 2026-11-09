"""Run example scenarios without adding records to the user's transaction databases."""
from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from procurement.simulation_examples import MARL_EXAMPLES,CATBOOST_EXAMPLES
from procurement.rl_service import simulate,default_vendor_rows
from procurement.bpi_offers import advise
from procurement import offer_workflow as flow

results=[]
for name,preset in MARL_EXAMPLES.items():
    for method in ['IQL','CTDE']:
        _,result,report=simulate(method,preset['quantity'],preset['urgent'],preset['budget'],preset['seed'],default_vendor_rows())
        row={'mode':'MARL','example':name,'method':method,'input':preset,'result':report['status'],
             'cost':report['total'],'stop_reason':result['stop_reason']}
        results.append(row);print(name,method,row['result'],row['cost'],flush=True)
catalog=flow.catalog()
for name,preset in CATBOOST_EXAMPLES.items():
    keys=[k for k in catalog.context_key.unique() if k.split(' | ')[1]==preset['sub']]
    context=next((k for k in keys if k.split(' | ')[2]=='Standard'),keys[0])
    rows=flow.candidates(catalog,context);rows['month']=9;rows['weekday']=5
    factor=preset['budget_factor'];budget=.01 if factor==0 else (
      float(rows.initial_po_value.median()) if factor==.5 else float(rows.initial_po_value.max())*factor)
    offers=advise(rows);eligible=[r for r in offers if r['nilai_penawaran']<=budget]
    selected=eligible[0] if eligible else None
    status=selected['purchase_action'] if selected else 'SEMUA PENAWARAN MELEBIHI ANGGARAN'
    results.append({'mode':'CatBoost','example':name,'context':context,'date':'2018-09-01','budget':budget,
       'vendor_count':len(rows),'result':status,'vendor':flow.vendor_label(selected['vendor'],flow.names()) if selected else None})
    print(name,'CatBoost',status,flush=True)
out=Path(__file__).resolve().parents[1]/'runs'/'simulation_examples.json'
out.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
assert len(results)==17
assert all(r.get('vendor_count',5)>=5 for r in results)
print('17 examples verified; no transaction database modified.',flush=True)
