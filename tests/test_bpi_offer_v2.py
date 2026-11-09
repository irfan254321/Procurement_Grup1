import unittest
from unittest.mock import patch
import pandas as pd
import numpy as np
from procurement.bpi_offers import advise,FEATURES
from procurement.bpi_offer_history import historical_rows
from procurement.bpi_offer_retrain import validation_choice
from procurement.bpi_offer_retrain import passes_gap_guard
from procurement.bpi_offer_retrain import document_accuracy_interval
from procurement.bpi_offer_history import export_history
import json
from pathlib import Path
import sqlite3
import tempfile


class FixedModel:
    classes_=np.array([0,1])
    def predict_proba(self,x):return np.tile([.6,.4],(len(x),1))


class OfferV2Tests(unittest.TestCase):
    def test_gap_guard_rejects_high_train_score_with_poor_validation(self):
        self.assertFalse(passes_gap_guard({'accuracy':.99,'macro_f1':.9},{'accuracy':.7,'macro_f1':.4}))
        self.assertTrue(passes_gap_guard({'accuracy':.9,'macro_f1':.7},{'accuracy':.88,'macro_f1':.68}))

    def test_serving_uses_saved_validation_threshold(self):
        model=FixedModel()
        metadata={'models':{'purchase':{'threshold':.3},'price_review':{'threshold':.7}},
                  'semantics':{'payment':{'0':'0-7 days','1':'7-30 days'}}}
        frame=pd.DataFrame([['c','v','area','sub','type','doc',100,1,0]],columns=FEATURES)
        with patch('procurement.bpi_offers.load_models',return_value=(dict.fromkeys(['purchase','price_review','payment'],model),metadata)):
            result=advise(frame)[0]
        self.assertEqual(result['purchase_action'],'LANJUTKAN KE REVIEW PEMBELIAN')
        self.assertEqual(result['price_action'],'TIDAK ADA SINYAL REVISI HARGA')

    def test_threshold_selection_depends_only_on_validation_labels(self):
        _,threshold,scores=validation_choice(FixedModel(),pd.DataFrame({'x':[1,2,3]}),np.array([1,1,0]))
        self.assertLessEqual(threshold,.4)
        self.assertAlmostEqual(scores['accuracy'],2/3)

    def test_company_history_filter_cannot_mix_vendor_or_company(self):
        snapshot={'cases':[{'company':'c1','vendor':'v1'},{'company':'c2','vendor':'v1'},
                           {'company':'c1','vendor':'v2'}]}
        self.assertEqual(historical_rows(snapshot,'c1','v1'),[snapshot['cases'][0]])
        self.assertEqual(historical_rows(snapshot,'missing'),[])

    def test_document_bootstrap_is_reproducible_and_handles_perfect_predictions(self):
        args=(['po1','po1','po2'],[0,1,1],[0,1,1])
        self.assertEqual(document_accuracy_interval(*args),[1.,1.])
        args=(['po1','po1','po2'],[0,1,1],[1,1,0])
        self.assertEqual(document_accuracy_interval(*args),document_accuracy_interval(*args))

    def test_completed_history_excludes_deleted_and_multiple_invoice_clearing(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'source.sqlite3';target=Path(folder)/'completed.json'
            db=sqlite3.connect(source)
            db.executescript('CREATE TABLE bpi_cases(case_id TEXT,document_id TEXT,attributes_json TEXT);'
              'CREATE TABLE bpi_events(case_id TEXT,event_index INTEGER,activity TEXT,timestamp TEXT,value REAL);')
            for case in ['clean','deleted','multiple']:
                db.execute('INSERT INTO bpi_cases VALUES(?,?,?)',(case,case,json.dumps({'Company':'c1','Vendor':'v1'})))
                activities=['Create Purchase Order Item','Record Invoice Receipt','Clear Invoice']
                if case=='deleted':activities+=['Delete Purchase Order Item']
                if case=='multiple':activities+=['Clear Invoice']
                db.executemany('INSERT INTO bpi_events VALUES(?,?,?,?,?)',[
                  (case,i,a,f'2018-01-{i+1:02d}T00:00:00+00:00',100.) for i,a in enumerate(activities)])
            db.commit();db.close()
            result=export_history(source,target)
            self.assertEqual([r['case_id'] for r in result['cases']],['clean'])
            self.assertEqual(result['cases'][0]['actual_payment_days'],1.)


if __name__=='__main__':unittest.main()
