import unittest
import json
from pathlib import Path
import pandas as pd
from procurement.vendor_display import aliases,vendor_name,display_text,NamedStreamlit,MARL_ALIASES
from procurement.simulation_examples import MARL_EXAMPLES,CATBOOST_EXAMPLES
from procurement import offer_workflow as flow


class SimulationExampleTests(unittest.TestCase):
    def test_all_vendor_aliases_are_unique_pt_names(self):
        mapping=aliases();self.assertEqual(len(mapping),1975)
        self.assertEqual(len(set(mapping.values())),len(mapping))
        self.assertTrue(all(v.startswith('PT. ') and not any(c.isdigit() for c in v) for v in mapping.values()))

    def test_old_trace_vendor_strings_receive_consistent_alias(self):
        text='vendor_0777 · vendorID_0817'
        self.assertEqual(display_text(text),vendor_name('vendorID_0817'))
        self.assertIn(MARL_ALIASES['B'],display_text('VMI memilih vendor B.'))

    def test_editor_returns_original_marl_ids_to_backend(self):
        class FakeUI:
            def data_editor(self,data,**kwargs):
                self.displayed=data;return data
        ui=FakeUI();wrapped=NamedStreamlit(ui)
        original=pd.DataFrame({'name':['A','B','C'],'capacity':[800,1200,600]})
        returned=wrapped.data_editor(original)
        self.assertEqual(list(ui.displayed.name),list(MARL_ALIASES.values()))
        self.assertEqual(list(returned.name),['A','B','C'])
        self.assertEqual(list(original.name),['A','B','C'])

    def test_marl_examples_have_valid_request_inputs(self):
        for p in MARL_EXAMPLES.values():
            self.assertTrue(0<=p['urgent']<=p['quantity'])
            self.assertGreater(p['budget'],0)

    def test_catboost_examples_resolve_to_five_source_vendors(self):
        data=flow.catalog()
        for p in CATBOOST_EXAMPLES.values():
            keys=[k for k in data.context_key.unique() if k.split(' | ')[1]==p['sub']]
            self.assertTrue(keys)
            self.assertGreaterEqual(flow.candidates(data,keys[0]).vendor.nunique(),5)


if __name__=='__main__':unittest.main()
