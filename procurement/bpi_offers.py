"""BPI-derived offer advice. Targets describe observed outcomes, not actual bid acceptance."""
from __future__ import annotations
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sqlite3
import numpy as np
import pandas as pd

from .bpi import DEFAULT_DB, ROOT, dataset_summary
from .bpi_training import split_documents

MODEL_DIR=ROOT/'runs'/'bpi_offers'
CATS=['company','vendor','spend_area','sub_spend_area','item_type','document_type']
NUMS=['initial_po_value','month','weekday']
FEATURES=CATS+NUMS
TASKS={'purchase':'Pelunasan vs penghapusan PO', 'price_review':'Revisi harga tercatat',
       'payment':'Kelompok jeda pembayaran'}


def opening_features(attrs,event):
    if event['value'] is None or not np.isfinite(event['value']) or event['value']<=0:
        return None
    ts=datetime.fromisoformat(event['timestamp'])
    names=['Company','Vendor','Spend area text','Sub spend area text','Item Type','Document Type']
    return {**{col:str(attrs.get(key) or '__MISSING__') for col,key in zip(CATS,names)},
            'initial_po_value':float(event['value']),'month':ts.month,'weekday':ts.weekday()}


def extract(source):
    db=sqlite3.connect(Path(source).resolve().as_uri()+'?mode=ro',uri=True)
    db.row_factory=sqlite3.Row
    try:
        mapping,split=split_documents(db)
        provenance=dataset_summary(db)
        summary={r['case_id']:dict(r) for r in db.execute('''SELECT case_id,
          SUM(activity='Clear Invoice') AS paid, SUM(activity='Delete Purchase Order Item') AS deleted,
          MAX(CASE WHEN activity='Delete Purchase Order Item' THEN event_index ELSE -1 END) AS delete_idx,
          MAX(CASE WHEN activity='Reactivate Purchase Order Item' THEN event_index ELSE -1 END) AS reactivate_idx,
          MAX(CASE WHEN activity='Change Price' THEN event_index ELSE -1 END) AS price_idx,
          SUM(activity='Record Invoice Receipt') AS invoices,
          MIN(CASE WHEN activity='Record Invoice Receipt' THEN timestamp END) AS invoice_ts,
          MIN(CASE WHEN activity='Clear Invoice' THEN timestamp END) AS clear_ts,
          MIN(CASE WHEN activity='Record Invoice Receipt' THEN event_index END) AS invoice_idx,
          MIN(CASE WHEN activity='Clear Invoice' THEN event_index END) AS clear_idx,
          SUM(activity IN ('Cancel Invoice Receipt','Cancel Subsequent Invoice',
          'Vendor creates debit memo','Record Subsequent Invoice','Change Currency')) AS corrections
          FROM bpi_events GROUP BY case_id''')}
        rows=[]; counts=Counter()
        query='''SELECT c.*,e.value,e.timestamp,e.event_index FROM bpi_cases c JOIN bpi_events e
              ON e.case_id=c.case_id WHERE e.activity='Create Purchase Order Item' ORDER BY c.case_id'''
        for c in db.execute(query):
            counts['all_cases']+=1
            f=opening_features(json.loads(c['attributes_json']),c)
            if f is None:
                counts['invalid_initial_value']+=1;continue
            s=summary[c['case_id']]
            buy=None
            if s['paid'] and not s['deleted']: buy=1
            elif not s['paid'] and s['deleted'] and s['delete_idx']>s['reactivate_idx']: buy=0
            price=int(s['price_idx']>c['event_index']) if s['paid'] and not s['deleted'] else None
            payment=None
            if s['paid']==s['invoices']==1 and not s['corrections'] and s['clear_idx']>s['invoice_idx']:
                days=(datetime.fromisoformat(s['clear_ts'])-datetime.fromisoformat(s['invoice_ts'])).total_seconds()/86400
                if days>=0: payment=0 if days<=7 else (1 if days<=30 else 2)
            for name,label in [('purchase',buy),('price_review',price),('payment',payment)]:
                if label is not None: counts[name+'_eligible_full_source']+=1
            group=mapping.get(c['document_id'])
            if group:
                rows.append({'case_id':c['case_id'],'document_id':c['document_id'],'partition':group,
                   **f,'purchase':buy,'price_review':price,'payment':payment})
        return pd.DataFrame(rows),dict(counts),split,provenance
    finally: db.close()


def train(source=DEFAULT_DB,out=MODEL_DIR,seed=42,iterations=150,max_train=30000):
    from catboost import CatBoostClassifier
    from sklearn.metrics import accuracy_score,f1_score,classification_report,confusion_matrix
    data,counts,split,provenance=extract(source)
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    catalog=data[data['partition']=='train'].groupby(CATS,dropna=False)['initial_po_value'].agg(['median','count']).reset_index()
    catalog=catalog.rename(columns={'median':'initial_po_value','count':'historical_items'})
    (out/'catalog.json').write_text(catalog.to_json(orient='records',force_ascii=False),encoding='utf-8')
    report={'task_version':1,'source_sha256':provenance['sha256'],'source':provenance['source'],
       'seed':seed,'features':FEATURES,'categorical_features':CATS,'split':split,'extraction':counts,
       'semantics':{'purchase':{'1':'Pelunasan tercatat tanpa penghapusan item',
                               '0':'Penghapusan tanpa pelunasan, tanpa reaktivasi sesudahnya'},
                    'price_review':{'1':'Change Price setelah PO dibuat','0':'Tidak teramati pada PO yang dibayar'},
                    'payment':{'0':'0–7 hari','1':'>7–30 hari','2':'>30 hari'}},'models':{},
       'limitations':['Label merupakan pendekatan hasil transaksi BPI, bukan penerimaan tawaran asli.',
         'Tidak ada nominal tawar balik, tenggat kontrak, cicilan, atau jaminan vendor paling optimal.',
         'Prediksi pada awal PO menggunakan snapshot kategori/vendor sebagai konteks yang diasumsikan diketahui.',
         'Nilai PO anonim, bukan harga per unit atau rupiah. Tidak ada unit mendesak pada sumber.',
         'Penghapusan dipakai sebagai label negatif usulan; alasan penolakan bisnis tidak tersedia.',
         'Kasus lintas cutoff dikeluarkan, sehingga kasus panjang/kompleks kurang terwakili.',
         'Skor model bukan tingkat persetujuan perusahaan atau probabilitas kausal.',
         'Pemilihan kandidat vendor mengikuti kategori historis; kesetaraan spesifikasi barang tidak dapat dibuktikan.']}
    manifests=[]
    for task in TASKS:
        eligible=data[data[task].notna()].copy()
        parts={g:eligible[eligible['partition']==g].copy() for g in ['train','validation','test']}
        if len(parts['train'])>max_train:
            parts['train']=parts['train'].sample(max_train,random_state=seed)
        if any(p.empty for p in parts.values()): raise ValueError('Partisi kosong: '+task)
        tr,va,te=(parts[g] for g in ['train','validation','test'])
        model=CatBoostClassifier(iterations=iterations,depth=5,learning_rate=.07,
          loss_function='MultiClass' if task=='payment' else 'Logloss',
          auto_class_weights='SqrtBalanced',random_seed=seed,thread_count=4,
          cat_features=CATS,allow_writing_files=False,verbose=50)
        print(task,{g:len(p) for g,p in parts.items()},flush=True)
        model.fit(tr[FEATURES],tr[task].astype(int),eval_set=(va[FEATURES],va[task].astype(int)),
          early_stopping_rounds=25,use_best_model=True)
        pred=model.predict(te[FEATURES]).reshape(-1).astype(int); y=te[task].astype(int)
        majority=int(tr[task].mode().iloc[0]); path=out/(task+'.cbm');model.save_model(str(path))
        report['models'][task]={'label_description':TASKS[task],
          'counts':{g:len(p) for g,p in parts.items()},
          'label_counts':{g:{str(int(k)):int(v) for k,v in p[task].value_counts().items()} for g,p in parts.items()},
          'accuracy':float(accuracy_score(y,pred)), 'macro_f1':float(f1_score(y,pred,average='macro',zero_division=0)),
          'baseline_accuracy':float(np.mean(y==majority)),
          'classification_report':classification_report(y,pred,zero_division=0,output_dict=True),
          'confusion_matrix':confusion_matrix(y,pred,labels=list(map(int,model.classes_))).tolist(),
          'trees':model.tree_count_,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
        for g,p in parts.items():
            m=p[['case_id','document_id','partition',task]].rename(columns={task:'label'}).copy()
            m['task']=task;manifests.append(m)
    # Reproducible feature/label data and audit registry for the trained offer models.
    db=sqlite3.connect(out/'training.sqlite3')
    try:
        data.to_sql('offer_samples',db,index=False,if_exists='replace')
        pd.concat(manifests).to_sql('evaluated_samples',db,index=False,if_exists='replace')
        db.execute('CREATE TABLE IF NOT EXISTS training_metadata(metadata_json TEXT)')
        db.execute('DELETE FROM training_metadata');db.execute('INSERT INTO training_metadata VALUES(?)',(json.dumps(report),))
        db.commit()
    finally: db.close()
    pd.concat(manifests).to_csv(out/'sample_manifest.csv',index=False)
    (out/'metrics.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({t:{k:v for k,v in m.items() if k in ['counts','accuracy','macro_f1','baseline_accuracy']} for t,m in report['models'].items()},indent=2),flush=True)
    return report


def load_models(model_dir=MODEL_DIR):
    from catboost import CatBoostClassifier
    model_dir=Path(model_dir)
    metadata=json.loads((model_dir/'metrics.json').read_text(encoding='utf-8'))
    if metadata['features']!=FEATURES or metadata['task_version']!=1:
        raise ValueError('Skema fitur model penawaran berbeda.')
    models={}
    for task in TASKS:
        p=model_dir/(task+'.cbm')
        if hashlib.sha256(p.read_bytes()).hexdigest()!=metadata['models'][task]['sha256']:
            raise ValueError('Checksum model berbeda: '+task)
        model=CatBoostClassifier();model.load_model(str(p));models[task]=model
    return models,metadata


def advise(frame,model_dir=MODEL_DIR):
    models,metadata=load_models(model_dir)
    if not np.isfinite(frame[NUMS].to_numpy(dtype=float)).all() or (frame['initial_po_value']<=0).any():
        raise ValueError('Nilai penawaran harus positif dan seluruh fitur angka harus terbatas.')
    results=[]
    for _,row in frame.iterrows():
        x=pd.DataFrame([row],columns=FEATURES)
        buy=models['purchase']; price=models['price_review'];pay=models['payment']
        bp=buy.predict_proba(x)[0];pp=price.predict_proba(x)[0];tp=pay.predict_proba(x)[0]
        b=int(bp[list(buy.classes_).index(1)]>=metadata['models']['purchase'].get('threshold',.5))
        p=int(pp[list(price.classes_).index(1)]>=metadata['models']['price_review'].get('threshold',.5))
        t=int(pay.classes_[int(np.argmax(tp))])
        results.append({'vendor':str(row['vendor']), 'nilai_penawaran':float(row['initial_po_value']),
          'purchase_score':float(bp[list(buy.classes_).index(1)]),
          'purchase_action':'LANJUTKAN KE REVIEW PEMBELIAN' if b==1 else 'TINJAU ULANG PENAWARAN',
          'price_revision_score':float(pp[list(price.classes_).index(1)]),
          'price_action':'TINJAU HARGA / MINTA REVISI' if p==1 else 'TIDAK ADA SINYAL REVISI HARGA',
          'payment_class':t,'payment_window':metadata['semantics']['payment'][str(t)]})
    return sorted(results,key=lambda x:-x['purchase_score'])
