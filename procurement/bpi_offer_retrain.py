"""Validation-only CatBoost selection with grouped temporal test evaluation."""
from pathlib import Path
import hashlib
import json
import sqlite3
import numpy as np
import pandas as pd
from catboost import CatBoostClassifier
from sklearn.metrics import accuracy_score,classification_report,confusion_matrix,f1_score
from .bpi_offers import FEATURES,CATS,TASKS


def evaluate(y,pred):
    return {'accuracy':float(accuracy_score(y,pred)),
            'macro_f1':float(f1_score(y,pred,average='macro',zero_division=0))}


def passes_gap_guard(training,validation):
    return training['accuracy']-validation['accuracy']<=.08 and training['macro_f1']-validation['macro_f1']<=.15


def document_accuracy_interval(documents,y,pred,seed=42,repeats=300):
    frame=pd.DataFrame({'document':np.asarray(documents),'correct':np.asarray(y)==np.asarray(pred)})
    summary=frame.groupby('document')['correct'].agg(['sum','count']).to_numpy()
    rng=np.random.default_rng(seed)
    estimates=[]
    for _ in range(repeats):
        sample=summary[rng.integers(0,len(summary),len(summary))].sum(axis=0)
        estimates.append(sample[0]/sample[1])
    return list(map(float,np.quantile(estimates,[.025,.975])))


def decisions(model,x,threshold=.5):
    prob=model.predict_proba(x)
    labels=np.asarray(model.classes_,dtype=int)
    if len(labels)==2:
        return np.where(prob[:,list(labels).index(1)]>=threshold,1,0)
    return labels[np.argmax(prob,axis=1)]


def validation_choice(model,x,y):
    probabilities=model.predict_proba(x)
    labels=np.asarray(model.classes_,dtype=int)
    candidates=[]
    for threshold in (np.arange(.10,.91,.05) if len(labels)==2 else [.5]):
        pred=np.where(probabilities[:,list(labels).index(1)]>=threshold,1,0) if len(labels)==2 else labels[probabilities.argmax(axis=1)]
        scores=evaluate(y,pred)
        # Minority classes matter: accuracy alone can favor an always-majority model.
        score=.65*scores['accuracy']+.35*scores['macro_f1']
        candidates.append((score,scores['accuracy'],-abs(threshold-.5),float(threshold),scores))
    best=max(candidates,key=lambda r:r[:3])
    return best[0],best[3],best[4]


def retrain(previous,out,iterations=350):
    previous=Path(previous);out=Path(out)
    if out.exists(): raise FileExistsError('Use a new version directory, preserve existing models.')
    out.mkdir(parents=True)
    db=sqlite3.connect(previous/'training.sqlite3')
    data=pd.read_sql_query('SELECT * FROM offer_samples',db);db.close()
    if data.groupby('document_id')['partition'].nunique().max()!=1:
        raise ValueError('Purchase document crosses partitions.')
    report=json.loads((previous/'metrics.json').read_text(encoding='utf-8'))
    previous_models=report['models']
    report['training_version']=2
    report['selection']={'criterion':'0.65 * validation accuracy + 0.35 * validation macro-F1',
      'test_policy':'Existing temporal test retained for comparison; never used for tuning or checkpoint selection. Not a new external test.',
      'regularization':'depth 2/3/4/6, L2 10–80, early stopping 40, best validation iteration; reject train-validation accuracy gap >.08 or macro-F1 gap >.15',
      'threshold':'Binary threshold selected only on validation; multiclass argmax.',
      'seed':42}
    report['models']={}; manifests=[]
    configs=[{'depth':4,'l2_leaf_reg':10,'auto_class_weights':None},
             {'depth':4,'l2_leaf_reg':20,'auto_class_weights':'SqrtBalanced'},
             {'depth':6,'l2_leaf_reg':20,'auto_class_weights':None},
             {'depth':6,'l2_leaf_reg':20,'auto_class_weights':'SqrtBalanced'}]
    for task in TASKS:
        frames={g:data[(data['partition']==g)&data[task].notna()].copy() for g in ['train','validation','test']}
        tr,va,te=(frames[g] for g in ['train','validation','test'])
        ytr,yva,yte=(f[task].astype(int) for f in (tr,va,te))
        print(task,{g:len(f) for g,f in frames.items()},flush=True)
        old=CatBoostClassifier();old.load_model(str(previous/(task+'.cbm')))
        oldscore,oldt,olds=validation_choice(old,va[FEATURES],yva)
        options=[{'name':'previous_model','model':old,'score':oldscore,'threshold':oldt,'validation':olds,
                  'parameters':{'training_rows':previous_models[task].get('fit_samples',previous_models[task]['counts']['train'])},'curves':None}]
        task_configs=configs+([{'depth':3,'l2_leaf_reg':40,'auto_class_weights':None},
          {'depth':3,'l2_leaf_reg':80,'auto_class_weights':None,'ignored_features':['vendor']},
          {'depth':2,'l2_leaf_reg':80,'auto_class_weights':None,'ignored_features':['vendor']}] if task=='payment' else [])
        for i,config in enumerate(task_configs):
            model=CatBoostClassifier(iterations=iterations,learning_rate=.045,random_seed=42,
              loss_function='MultiClass' if task=='payment' else 'Logloss',cat_features=CATS,
              thread_count=4,allow_writing_files=False,verbose=100,**config)
            model.fit(tr[FEATURES],ytr,eval_set=(va[FEATURES],yva),early_stopping_rounds=40,use_best_model=True)
            score,threshold,metrics=validation_choice(model,va[FEATURES],yva)
            options.append({'name':f'candidate_{i+1}','model':model,'score':score,'threshold':threshold,
                            'validation':metrics,'parameters':config,'curves':model.get_evals_result()})
            print(task,options[-1]['name'],'validation',metrics,'threshold',threshold,flush=True)
        # All configurations and thresholds are frozen before inspecting test predictions.
        for option in options:
            option['training_metrics']=evaluate(ytr,decisions(option['model'],tr[FEATURES],option['threshold']))
            option['passes_gap_guard']=passes_gap_guard(option['training_metrics'],option['validation'])
        eligible=[o for o in options if o['passes_gap_guard']]
        if not eligible:raise ValueError('Tidak ada kandidat lolos pemeriksaan selisih train-validasi: '+task)
        champion=max(eligible,key=lambda o:(o['score'],-o['model'].tree_count_))
        model=champion['model'];threshold=champion['threshold']
        train_metrics=evaluate(ytr,decisions(model,tr[FEATURES],threshold))
        validation_metrics=champion['validation']
        test_pred=decisions(model,te[FEATURES],threshold)
        test_metrics=evaluate(yte,test_pred)
        majority=int(ytr.mode().iloc[0]);baseline=evaluate(yte,np.repeat(majority,len(yte)))
        path=out/(task+'.cbm');model.save_model(str(path))
        report['models'][task]={'label_description':TASKS[task],**test_metrics,
          'baseline_accuracy':baseline['accuracy'],'baseline_macro_f1':baseline['macro_f1'],
          'counts':{g:len(f) for g,f in frames.items()},
          'label_counts':{g:{str(int(k)):int(v) for k,v in f[task].value_counts().items()} for g,f in frames.items()},
          'classification_report':classification_report(yte,test_pred,output_dict=True,zero_division=0),
          'test_accuracy_document_bootstrap_95ci':document_accuracy_interval(te['document_id'],yte,test_pred),
          'confusion_matrix':confusion_matrix(yte,test_pred,labels=list(map(int,model.classes_))).tolist(),
          'trees':model.tree_count_,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
          'fit_samples':champion['parameters']['training_rows'] if champion['name']=='previous_model' else len(tr),
          'threshold':threshold,'selected_candidate':champion['name'],
          'training_metrics':train_metrics,'validation_metrics':validation_metrics,
          'generalization_gap_accuracy':train_metrics['accuracy']-validation_metrics['accuracy'],
          'generalization_gap_macro_f1':train_metrics['macro_f1']-validation_metrics['macro_f1'],
          'overfit_warning':train_metrics['accuracy']-validation_metrics['accuracy']>.08 or train_metrics['macro_f1']-validation_metrics['macro_f1']>.15,
          'temporal_test_gap_accuracy':validation_metrics['accuracy']-test_metrics['accuracy'],
          'temporal_test_warning':validation_metrics['accuracy']-test_metrics['accuracy']>.08,
          'selection_candidates':[{k:v for k,v in o.items() if k not in ['model','curves']} for o in options],
          'learning_curves':champion['curves']}
        for g,f in frames.items():
            m=f[['case_id','document_id','partition',task]].rename(columns={task:'label'}).copy();m['task']=task;manifests.append(m)
        print('FROZEN TEST',task,test_metrics,flush=True)
    catalog=data[data['partition']=='train'].groupby(CATS)['initial_po_value'].agg(['median','count']).reset_index().rename(columns={'median':'initial_po_value','count':'historical_items'})
    (out/'catalog.json').write_text(catalog.to_json(orient='records',force_ascii=False),encoding='utf-8')
    pd.concat(manifests).to_csv(out/'sample_manifest.csv',index=False)
    (out/'metrics.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    import shutil
    shutil.copyfile(previous/'training.sqlite3',out/'training.sqlite3')
    d=sqlite3.connect(out/'training.sqlite3')
    with d:
        pd.concat(manifests).to_sql('evaluated_samples',d,index=False,if_exists='replace')
        d.execute('DELETE FROM training_metadata');d.execute('INSERT INTO training_metadata VALUES(?)',(json.dumps(report),))
    d.close()
    return report
