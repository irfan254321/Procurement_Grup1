from pathlib import Path
import json,sqlite3,sys
import pandas as pd
from catboost import CatBoostClassifier
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder,StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.tree import DecisionTreeClassifier
from sklearn.svm import LinearSVC
from sklearn.metrics import accuracy_score,f1_score,classification_report
from joblib import dump

ROOT=Path(__file__).resolve().parent
source=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT
out=ROOT/'runs'/'agent_benchmark';out.mkdir(parents=True,exist_ok=True)
with sqlite3.connect((source/'runs/bpi_offers/training.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
    data=pd.read_sql_query('select * from offer_samples',db)
with sqlite3.connect((source/'data/bpi2019.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
    revised={r[0] for r in db.execute("select q.case_id from bpi_events q join bpi_events p on p.case_id=q.case_id and p.activity='Create Purchase Order Item' where q.activity='Change Quantity' and q.event_index>p.event_index")}
data['intake']=data.case_id.isin(revised).astype(int).where(data.purchase.eq(1))
assert data.groupby('document_id').partition.nunique().max()==1
cats=['company','vendor','spend_area','sub_spend_area','item_type','document_type']; nums=['initial_po_value','month','weekday']
tasks={'IRE':('intake','Tinjau kebutuhan: prediksi revisi jumlah setelah PO dibuat'), 'VMI':('purchase','Nilai risiko transaksi vendor: pelunasan vs penghapusan PO'), 'DA':('price_review','Tinjau penawaran: prediksi kejadian revisi harga'), 'SLM':('payment','Perkirakan jeda pembayaran: ≤7, >7–30, atau >30 hari')}
report={}
for agent,(target,role) in tasks.items():
    cols=[c for c in cats if c!='vendor' or agent!='IRE']; features=cols+nums
    prep=lambda:ColumnTransformer([('cat',OneHotEncoder(handle_unknown='ignore'),cols),('num',StandardScaler(),nums)])
    models={'Decision Tree':make_pipeline(prep(),DecisionTreeClassifier(max_depth=8,min_samples_leaf=40,class_weight='balanced',random_state=42)), 'CatBoost':CatBoostClassifier(iterations=120,depth=4,l2_leaf_reg=20,learning_rate=.06,auto_class_weights='SqrtBalanced',cat_features=cols,thread_count=4,random_seed=42,verbose=False,allow_writing_files=False), 'SVM (linear)':make_pipeline(prep(),LinearSVC(C=.1,class_weight='balanced',max_iter=5000,random_state=42))}
    tr,va,te=[data[(data.partition==p)&data[target].notna()] for p in ('train','validation','test')]; y=lambda d:d[target].astype(int)
    r={'role':role,'target':target,'features':features,'train':len(tr),'validation':len(va),'test':len(te),'baseline':float((y(te)==y(tr).mode().iloc[0]).mean()),'models':{}}
    for name,model in models.items():
        args={'eval_set':(va[features],y(va)),'early_stopping_rounds':20} if name=='CatBoost' else {}
        model.fit(tr[features],y(tr),**args)
        metrics={}
        for part,d in [('train',tr),('validation',va),('test',te)]:
            pred=model.predict(d[features]).reshape(-1).astype(int)
            metrics[part]={'accuracy':accuracy_score(y(d),pred),'macro_f1':f1_score(y(d),pred,average='macro',zero_division=0),'classes':classification_report(y(d),pred,output_dict=True,zero_division=0)}
        r['models'][name]=metrics;dump(model,out/f'{agent}_{name.split()[0]}.joblib',compress=3)
        print(agent,name,metrics['test']['accuracy'],metrics['test']['macro_f1'],flush=True)
    r['recommended']=max(r['models'],key=lambda name:r['models'][name]['validation']['macro_f1']);report[agent]=r
(out/'results.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
