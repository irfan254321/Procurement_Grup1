"""Ten BPI-based scenarios with explicitly assumed commercial rules."""
import hashlib
import json
import sqlite3
import pandas as pd

MODELS={'IRE':'SVM (linear)','VMI':'XGBoost','DA':'Extra Trees','SLM':'CatBoost'}
SCENARIOS=[('Products for Resale','Standard'),('Labels','Standard'),
 ('Metal Containers & Lids < 30L','Standard'),('Plastic Containers & Lids < 30L','Standard'),
 ('Trading products (old structure)','Standard'),('Extenders','Standard'),('Road Packed','Service'),
 ('MRO (components)','Standard'),('Surfactants','Standard'),('Laboratory Supplies & Services','Standard')]
DEFAULT={'quantity':10,'horizon_months':0,'deadline_days':21,'payment_days':30}

def scenarios(root):
    rows=pd.read_json(root/'runs/bpi_offers/catalog.json')
    rows=rows[(rows.company=='companyID_0000') & (rows.document_type=='Standard PO')]
    result={}
    for name,kind in SCENARIOS:
        pool=rows[(rows.sub_spend_area==name)&(rows.item_type==kind)]
        groups=[g.drop_duplicates('vendor') for _,g in pool.groupby('spend_area')]
        g=max(groups,key=len)
        if len(g)<5:raise ValueError('Katalog tidak punya lima vendor: '+name)
        result[name]=g.sort_values(['historical_items','vendor'],ascending=[False,True]).head(5)
    return result

def rules(root,category,frame):
    names=json.loads((root/'runs/bpi_offers/vendor_aliases.json').read_text(encoding='utf-8'))
    path=root/'data/web_procurement.sqlite3';path.parent.mkdir(exist_ok=True)
    db=sqlite3.connect(path,timeout=15)
    try:
        with db:
            db.execute('''CREATE TABLE IF NOT EXISTS negotiation_vendor_rules(
              category TEXT NOT NULL, vendor_id TEXT NOT NULL, rule_json TEXT NOT NULL,
              PRIMARY KEY(category,vendor_id))''')
            for i,v in enumerate(frame.itertuples()):
                token=int(hashlib.sha256(v.vendor.encode()).hexdigest()[:8],16)
                base=max(1.,float(v.initial_po_value)); margin=(10+token%7)/100
                # A historical item value anchors scale only. All other inputs
                # are scenario assumptions, including the unit count of 10.
                value={'vendor_id':v.vendor,'vendor':names[v.vendor],
                    'unit_cost_now':round(base*.66/10,2),'monthly_cost_change':(1+token%4)/100,
                    'labor_cost_per_unit':round(base*.12/10,2),'shipping_cost':round(base*.07,2),
                    'overhead_cost':round(base*.025,2),'min_margin':margin,
                    'opening_margin':round(margin+.12,2),'max_discount':.10+(token%11)/100,
                    'working_capital':round(base*(1.05+(token%8)/10),2),
                    'capacity':10+token%31,'delivery_days':3+token%13,'max_payment_days':30+(token%4)*15,
                    'quality':.70+(token%26)/100,'risk':.16+(token%15)/100,
                    'source':'Asumsi simulasi, skala dari nilai PO anonim BPI'}
                db.execute('INSERT OR IGNORE INTO negotiation_vendor_rules VALUES(?,?,?)',
                           (category,v.vendor,json.dumps(value)))
        found=dict(db.execute('SELECT vendor_id,rule_json FROM negotiation_vendor_rules WHERE category=?',(category,)))
        return [json.loads(found[v]) for v in frame.vendor]
    finally:db.close()
