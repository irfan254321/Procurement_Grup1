"""Add diagnostics after frozen model selection; never change selected models."""
from pathlib import Path
import json
import sqlite3
import sys
import pandas as pd
from catboost import CatBoostClassifier
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from procurement.bpi_offers import FEATURES
from procurement.bpi_offer_retrain import decisions,document_accuracy_interval

root=Path(__file__).resolve().parents[1]
out=root/'runs'/'bpi_offers'
metadata=json.loads((out/'metrics.json').read_text(encoding='utf-8'))
previous_path=root/'previous_metrics.json'
if previous_path.exists():
    previous=json.loads(previous_path.read_text(encoding='utf-8'))
    metadata['previous_metrics']={t:{k:m[k] for k in ['accuracy','macro_f1','baseline_accuracy']}
                                  for t,m in previous['models'].items()}
d=sqlite3.connect(out/'training.sqlite3')
data=pd.read_sql_query('SELECT * FROM offer_samples',d)
for task,m in metadata['models'].items():
    m['fit_samples']=30000 if m['selected_candidate']=='previous_model' else m['counts']['train']
    m['temporal_test_gap_accuracy']=m['validation_metrics']['accuracy']-m['accuracy']
    m['temporal_test_warning']=m['temporal_test_gap_accuracy']>.08
    test=data[(data['partition']=='test')&data[task].notna()]
    model=CatBoostClassifier();model.load_model(str(out/(task+'.cbm')))
    pred=decisions(model,test[FEATURES],m['threshold'])
    m['test_accuracy_document_bootstrap_95ci']=document_accuracy_interval(test['document_id'],test[task].astype(int),pred)
    print(task,{k:m[k] for k in ['accuracy','macro_f1','selected_candidate','training_metrics','validation_metrics',
                               'overfit_warning','temporal_test_warning','test_accuracy_document_bootstrap_95ci']})
(out/'metrics.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
with d:
    d.execute('DELETE FROM training_metadata');d.execute('INSERT INTO training_metadata VALUES(?)',(json.dumps(metadata),))
d.close()
