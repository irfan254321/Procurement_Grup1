from collections import defaultdict
import json
from pathlib import Path
import sqlite3

root=Path('C:/Users/Study/Documents/Koding/multi-agent-procurement')
db=sqlite3.connect((root/'data/bpi2019.sqlite3').as_uri()+'?mode=ro',uri=True)
db.row_factory=sqlite3.Row
flags={row['case_id']:dict(row) for row in db.execute('''
 SELECT case_id,
 MAX(activity='Clear Invoice') AS paid,
 MAX(activity='Record Goods Receipt') AS goods_received,
 MAX(activity='Delete Purchase Order Item') AS deletion_recorded,
 MAX(activity='Reactivate Purchase Order Item') AS reactivation_recorded,
 MAX(activity='Change Price') AS price_revision,
 MAX(CASE WHEN activity='Clear Invoice' THEN event_index ELSE -1 END) AS last_paid,
 MAX(CASE WHEN activity='Delete Purchase Order Item' THEN event_index ELSE -1 END) AS last_deleted,
 MAX(CASE WHEN activity='Reactivate Purchase Order Item' THEN event_index ELSE -1 END) AS last_reactivated
 FROM bpi_events GROUP BY case_id''')}
groups=defaultdict(lambda:{'cases':0,'documents':set(),'vendors':set(),'paid':0,'goods_received':0,
 'deletion_recorded':0,'reactivation_recorded':0,'price_revision':0,'last_explicit_status_deleted':0,
 'paid_without_deletion':0,'paid_and_deletion':0,'neither_paid_nor_deleted':0})
for c in db.execute('select case_id,document_id,vendor,attributes_json from bpi_cases'):
    company=json.loads(c['attributes_json']).get('Company','__MISSING__')
    for key in (company,'ALL'):
        g=groups[key]; f=flags[c['case_id']]
        g['cases']+=1;g['documents'].add(c['document_id']);g['vendors'].add(c['vendor'])
        for name in ('paid','goods_received','deletion_recorded','reactivation_recorded','price_revision'):
            g[name]+=f[name]
        g['last_explicit_status_deleted']+=int(f['last_deleted']>f['last_reactivated'])
        g['paid_without_deletion']+=int(f['paid'] and not f['deletion_recorded'])
        g['paid_and_deletion']+=int(f['paid'] and f['deletion_recorded'])
        g['neither_paid_nor_deleted']+=int(not f['paid'] and not f['deletion_recorded'])
result=[]
for name,g in sorted(groups.items()):
    n=g['cases']; g['documents']=len(g['documents']);g['vendors']=len(g['vendors'])
    result.append({'company':name,**g,'paid_percent_of_po_items':round(100*g['paid']/n,4),
        'goods_received_percent_of_po_items':round(100*g['goods_received']/n,4),
        'deletion_recorded_percent_of_po_items':round(100*g['deletion_recorded']/n,4)})
output={'definition':'Observed Clear Invoice cases divided by PO-item cases. NOT vendor-offer acceptance rate.',
 'unit':'purchase-order item (case), not tender offer or supplier',
 'company_count':len(groups)-1,'companies':result,
 'limitations':['Vendor offers rejected before PO creation are absent.',
 'No payment observed does not prove rejection; observation may be incomplete.',
 'Goods receipt, payment and deletion flags can overlap.',
 'Company and vendor identities are anonymized.']}
dest=Path('C:/Users/Study/AppData/Local/Temp/BPI_COMPANY_DECISIONS.json')
dest.write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(output,indent=2))
