"""Meaningful checks against the trained offer artifacts and observed-source feature contract."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from procurement.bpi_offers import FEATURES,MODEL_DIR,advise,opening_features
import pandas as pd

manifest=pd.read_csv(MODEL_DIR/'sample_manifest.csv',dtype={'document_id':str})
assert manifest.groupby('document_id')['partition'].nunique().max()==1,'PO leaked between partitions'
assert not set(FEATURES)&{'purchase','payment','price_review','case_id','document_id','partition'}
attributes={'Company':'c','Vendor':'v'}
event={'value':100,'timestamp':'2018-01-01T12:00:00+00:00'}
before=opening_features(attributes,event)
attributes['Clear Invoice']='future';attributes['final_outcome']=1
assert opening_features(attributes,event)==before
catalog=pd.read_json(MODEL_DIR/'catalog.json').head(3)
catalog['month']=1;catalog['weekday']=0
first=advise(catalog);second=advise(catalog)
assert first==second,'Reload changed predictions'
assert len(first)==len(catalog)
assert all(0<=r['purchase_score']<=1 and r['payment_class'] in (0,1,2) for r in first)
invalid=catalog.copy();invalid['initial_po_value']=-1
try: advise(invalid)
except ValueError: pass
else: raise AssertionError('Negative offer accepted')
print('PASS: disjoint documents, no future-label features, prefix independence, reload parity, valid predictions and input rejection')
