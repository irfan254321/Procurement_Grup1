import tempfile
from pathlib import Path
import unittest
from procurement import offer_workflow as flow


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.db=flow.connect(Path(self.tmp.name)/'test.sqlite3')
        self.catalog=flow.catalog();self.context=next(iter(self.catalog.context_key))
        self.rows=flow.candidates(self.catalog,self.context)
        self.request={'context_key':self.context,'request_name':'Test request','budget':1e12,'date':'2018-09-01'}
    def tearDown(self):self.db.close();self.tmp.cleanup()

    def test_every_selectable_request_has_five_real_source_vendors(self):
        for key in self.catalog.context_key.unique():
            rows=flow.candidates(self.catalog,key)
            self.assertGreaterEqual(rows.vendor.nunique(),5)
            self.assertEqual(set(rows.company),{flow.COMPANY_ID})

    def test_persisted_trace_changes_only_when_step_is_reached(self):
        rid=flow.create_run(self.db,self.rows,self.request);r=flow.load_run(self.db,rid)
        self.assertEqual(len(r['events']),17)
        self.assertEqual(r['company_name'],'PT. Biz Indonesia Market')
        first=flow.visible_vendor_rows(r,1)
        self.assertTrue(all(x['Status']=='Belum diperiksa' and x['Skor model']=='—' and x['Pembayaran']=='—' for x in first))
        second=flow.visible_vendor_rows(r,2)
        self.assertEqual(sum(x['Skor model']!='—' for x in second),1)
        self.assertTrue(all(x['Pembayaran']=='—' for x in second))
        final=flow.visible_vendor_rows(r,17)
        self.assertEqual(sum(x['Status']=='Kandidat terpilih' for x in final),1)
        self.assertTrue(all(x['Pembayaran']!='—' for x in final))
        self.assertEqual(flow.runs(self.db)[0]['id'],rid)

    def test_decisions_are_saved_with_history(self):
        rid=flow.create_run(self.db,self.rows,self.request)
        flow.review(self.db,rid,'DISETUJUI');flow.review(self.db,rid,'DITOLAK')
        self.assertEqual(flow.load_run(self.db,rid)['review_decision'],'DITOLAK')
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM offer_workflow_reviews').fetchone()[0],2)

    def test_no_candidate_above_budget_can_be_approved(self):
        request={**self.request,'budget':.0001}
        rid=flow.create_run(self.db,self.rows,request)
        self.assertIsNone(flow.load_run(self.db,rid)['results']['selected'])
        with self.assertRaises(ValueError):flow.review(self.db,rid,'DISETUJUI')

    def test_config_requires_five_and_category_membership(self):
        vendors=list(self.rows.vendor);values=dict(zip(vendors,self.rows.initial_po_value))
        with self.assertRaises(ValueError):flow.save_settings(self.db,self.context,vendors[:4],values,vendors)
        with self.assertRaises(ValueError):flow.save_settings(self.db,self.context,vendors+['invented'],values,vendors)
        flow.save_settings(self.db,self.context,vendors,values,vendors)
        self.assertEqual(set(flow.load_settings(self.db,self.context)['vendors']),set(vendors))


if __name__=='__main__':unittest.main()
