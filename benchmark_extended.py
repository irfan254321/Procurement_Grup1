from pathlib import Path
import json,sqlite3,sys
import numpy as np
import pandas as pd
from joblib import dump
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder,StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.linear_model import LogisticRegression,SGDClassifier
from sklearn.ensemble import RandomForestClassifier,ExtraTreesClassifier,AdaBoostClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.cluster import MiniBatchKMeans,Birch
from sklearn.mixture import GaussianMixture
from sklearn.decomposition import TruncatedSVD
from sklearn.metrics import accuracy_score,f1_score,classification_report,silhouette_score,adjusted_rand_score
from xgboost import XGBClassifier

root=Path(__file__).resolve().parent;source=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else root
out=root/'runs/agent_benchmark'; report=json.loads((out/'results.json').read_text(encoding='utf-8'))
with sqlite3.connect((source/'runs/bpi_offers/training.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
    data=pd.read_sql_query('select * from offer_samples',db)
with sqlite3.connect((source/'data/bpi2019.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
    revised={r[0] for r in db.execute("select q.case_id from bpi_events q join bpi_events p on p.case_id=q.case_id and p.activity='Create Purchase Order Item' where q.activity='Change Quantity' and q.event_index>p.event_index")}
data['intake']=data.case_id.isin(revised).astype(int).where(data.purchase.eq(1))
assert data.groupby('document_id').partition.nunique().max()==1
cluster_report={}
for agent,r in report.items():
    target=r['target']; features=r['features']; nums=['initial_po_value','month','weekday']; cats=[c for c in features if c not in nums]
    parts={k:data[(data.partition==k)&data[target].notna()] for k in ['train','validation','test']}
    assert [len(parts[k]) for k in parts]==[r[k] for k in parts]
    X={k:p[features] for k,p in parts.items()}; y={k:p[target].astype(int) for k,p in parts.items()}
    def prep():return ColumnTransformer([('cat',OneHotEncoder(handle_unknown='ignore'),cats),('num',StandardScaler(),nums)])
    models={
      'Logistic Regression':LogisticRegression(C=.5,class_weight='balanced',max_iter=500),
      'Random Forest':RandomForestClassifier(n_estimators=64,max_depth=14,min_samples_leaf=12,class_weight='balanced_subsample',n_jobs=4,random_state=42),
      'Extra Trees':ExtraTreesClassifier(n_estimators=64,max_depth=18,min_samples_leaf=10,class_weight='balanced',n_jobs=4,random_state=42),
      'SGD log-loss':SGDClassifier(loss='log_loss',class_weight='balanced',alpha=.001,random_state=42),
      'AdaBoost':AdaBoostClassifier(estimator=DecisionTreeClassifier(max_depth=2,min_samples_leaf=40,random_state=42),n_estimators=50,random_state=42),
      'XGBoost':XGBClassifier(n_estimators=120,max_depth=4,learning_rate=.08,reg_lambda=10,n_jobs=4,random_state=42)}
    def score(name,model):
        model.fit(X['train'],y['train']); metrics={}
        for k in parts:
            pred=model.predict(X[k]).reshape(-1).astype(int)
            metrics[k]={'accuracy':accuracy_score(y[k],pred),'macro_f1':f1_score(y[k],pred,average='macro',zero_division=0),'classes':classification_report(y[k],pred,output_dict=True,zero_division=0)}
        key=name.split()[0];dump(model,out/f'{agent}_{key}.joblib',compress=3);r['models'][name]=metrics
        print(agent,name,round(metrics['test']['accuracy'],4),round(metrics['test']['macro_f1'],4),flush=True)
    for name,m in models.items():score(name,make_pipeline(prep(),m))
    embedding=make_pipeline(prep(),TruncatedSVD(n_components=8,random_state=42),StandardScaler())
    z=embedding.fit_transform(X['train']); zv=embedding.transform(X['validation']);zt=embedding.transform(X['test'])
    rng=np.random.default_rng(42); fit=z[rng.choice(len(z),min(10000,len(z)),replace=False)]
    cr={}
    for name,m in {'MiniBatch K-means':MiniBatchKMeans(n_clusters=5,n_init=3,random_state=42),'Gaussian mixture':GaussianMixture(n_components=5,covariance_type='diag',max_iter=70,random_state=42),'BIRCH':Birch(n_clusters=5,threshold=1.25)}.items():
        m.fit(fit); validation=m.predict(zv);test=m.predict(zt)
        sil=lambda a,b:float(silhouette_score(a,b,sample_size=min(1200,len(a)),random_state=42)) if 1<len(set(b))<len(b) else None
        cr[name]={'validation_silhouette':sil(zv,validation),'test_silhouette':sil(zt,test),'test_sizes':{str(k):int(v) for k,v in pd.Series(test).value_counts().items()},'ari_proxy_test':float(adjusted_rand_score(y['test'],test))}
    # Same classifier and original features; the only change is an unsupervised distance block.
    # K-means and its preprocessing are fit inside the pipeline on training rows only.
    cluster_block=make_pipeline(prep(),TruncatedSVD(n_components=8,random_state=42),StandardScaler(),MiniBatchKMeans(n_clusters=5,n_init=3,random_state=42))
    from sklearn.pipeline import FeatureUnion
    score('Cluster+Logistic',make_pipeline(FeatureUnion([('original',prep()),('distances',cluster_block)]),LogisticRegression(C=.5,class_weight='balanced',max_iter=500)))
    cluster_report[agent]=cr;r['recommended']=max(r['models'],key=lambda n:r['models'][n]['validation']['macro_f1'])
    print(agent,'clusters',cr,flush=True)
    (out/'results.progress.json').write_text(json.dumps(report,ensure_ascii=False),encoding='utf-8')
(out/'results.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
(out/'clustering.json').write_text(json.dumps(cluster_report,indent=2,ensure_ascii=False),encoding='utf-8')
