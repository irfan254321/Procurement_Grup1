"""Address the measured train-validation macro-F1 gap, without selecting by test."""
from pathlib import Path
import sys,json,hashlib,sqlite3
import pandas as pd
import numpy as np
from catboost import CatBoostClassifier
from sklearn.metrics import classification_report,confusion_matrix
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from procurement.bpi_offers import FEATURES,CATS
from procurement.bpi_offer_retrain import evaluate,decisions,validation_choice,document_accuracy_interval

out=Path(__file__).resolve().parents[1]/'runs'/'bpi_offers'
report=json.loads((out/'metrics.json').read_text(encoding='utf-8'))
d=sqlite3.connect(out/'training.sqlite3');data=pd.read_sql_query('SELECT * FROM offer_samples WHERE payment IS NOT NULL',d)
parts={g:data[data['partition']==g] for g in ['train','validation','test']}
tr,va,te=(parts[g] for g in parts); yt,yv,ye=(f.payment.astype(int) for f in (tr,va,te))
candidates=[];log=[]
for depth,l2,ignore in [(3,40,False),(3,80,True),(2,80,True)]:
    model=CatBoostClassifier(iterations=250,depth=depth,l2_leaf_reg=l2,learning_rate=.04,
      loss_function='MultiClass',random_seed=42,cat_features=CATS,thread_count=4,
      ignored_features=['vendor'] if ignore else [],allow_writing_files=False,verbose=100)
    model.fit(tr[FEATURES],yt,eval_set=(va[FEATURES],yv),early_stopping_rounds=30,use_best_model=True)
    score,threshold,validation=validation_choice(model,va[FEATURES],yv)
    training=evaluate(yt,decisions(model,tr[FEATURES]))
    passed=training['accuracy']-validation['accuracy']<=.08 and training['macro_f1']-validation['macro_f1']<=.15
    entry={'depth':depth,'l2_leaf_reg':l2,'ignore_vendor':ignore,'train':training,'validation':validation,'passed_gap_guard':passed,'validation_score':score}
    log.append(entry);print(entry,flush=True)
    if passed:candidates.append((score,-model.tree_count_,model,training,validation,entry))
if not candidates:raise RuntimeError('No payment model passes gap guard; leave artifacts unchanged.')
_,_,model,training,validation,chosen=max(candidates,key=lambda x:x[:2])
# Only after the train/validation guard and ranking are frozen, score the temporal test.
pred=decisions(model,te[FEATURES]);scores=evaluate(ye,pred)
model.save_model(str(out/'payment.cbm'))
m=report['models']['payment'];m.update(scores)
m.update({'sha256':hashlib.sha256((out/'payment.cbm').read_bytes()).hexdigest(),
 'trees':model.tree_count_,'selected_candidate':'regularized_payment_gap_guard',
 'threshold':.5,'training_metrics':training,'validation_metrics':validation,
 'generalization_gap_accuracy':training['accuracy']-validation['accuracy'],
 'generalization_gap_macro_f1':training['macro_f1']-validation['macro_f1'],
 'overfit_warning':False,'temporal_test_gap_accuracy':validation['accuracy']-scores['accuracy'],
 'temporal_test_warning':validation['accuracy']-scores['accuracy']>.08,
 'classification_report':classification_report(ye,pred,output_dict=True,zero_division=0),
 'confusion_matrix':confusion_matrix(ye,pred,labels=list(map(int,model.classes_))).tolist(),
 'learning_curves':model.get_evals_result(),'payment_regularization_candidates':log,
 'selected_regularization':chosen,'test_accuracy_document_bootstrap_95ci':document_accuracy_interval(te.document_id,ye,pred)})
report['selection']['payment_followup']='Additional depth 2/3 regularized candidates after train-validation macro-F1 gap exceeded .15. Selection uses train/validation only. Temporal test is reused for diagnostic reporting, not a new independent assessment.'
(out/'metrics.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
with d:
    d.execute('DELETE FROM training_metadata');d.execute('INSERT INTO training_metadata VALUES(?)',(json.dumps(report),))
d.close();print('PAYMENT FROZEN',scores,'train',training,'validation',validation,flush=True)
