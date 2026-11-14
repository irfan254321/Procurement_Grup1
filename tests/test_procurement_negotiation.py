import unittest
from decimal import Decimal
from procurement_negotiation import negotiate


def vendor(**changes):
    return {'vendor_id':'v1','vendor':'PT. Contoh','unit_cost_now':10,'monthly_cost_change':'.10',
            'labor_cost_per_unit':2,'shipping_cost':6,'overhead_cost':2,'min_margin':'.10',
            'opening_margin':'.20','working_capital':1000,'capacity':20,'delivery_days':5,
            'max_payment_days':30,'quality':'.85','risk':'.1', **changes}


class NegotiationTests(unittest.TestCase):
    def test_forecast_costs_and_minimum_are_reconciled(self):
        r=negotiate([vendor()],200,10,2)
        v=r['vendors'][0]; c=v['costs']
        self.assertEqual(c['unit_cost_forecast'],12.10)
        self.assertEqual(c['goods_total'],121)
        self.assertEqual(c['labor_total'],20)
        self.assertEqual(c['total_cost'],149)
        self.assertEqual(r['minimum_budget'],165.56)
        self.assertGreaterEqual(v['realized_margin'],.1)
        self.assertLessEqual(v['final_offer'],r['budget'])

    def test_same_vendor_different_budget_changes_outcome(self):
        lo=negotiate([vendor()],142.22,10)
        hi=negotiate([vendor()],142.23,10)
        self.assertEqual(lo['minimum_budget'],142.23)
        self.assertEqual(lo['status'],'budget_conflict')
        self.assertEqual(lo['vendors'][0]['rounds'][-1]['action'],'reject')
        self.assertEqual(hi['status'],'agreement')
        self.assertEqual(hi['recommended']['final_offer'],142.23)
        self.assertIsNone(lo['recommended'])

    def test_vendor_rules_filter_even_high_budget(self):
        r=negotiate([vendor(working_capital=120,capacity=9,delivery_days=15,max_payment_days=20)],10000,10,deadline_days=10)
        self.assertEqual(r['status'],'no_feasible_vendor')
        self.assertIsNone(r['minimum_budget'])
        self.assertEqual(len(r['vendors'][0]['constraints']),4)
        self.assertIsNone(r['vendors'][0]['score'])
        self.assertFalse(r['vendors'][0]['rounds'])

    def test_discount_rule_can_be_stricter_than_margin(self):
        r=negotiate([vendor(max_discount='.01')],150,10)
        v=r['vendors'][0]
        self.assertEqual(v['vendor_floor'],142.23)
        self.assertEqual(v['opening_offer'],160)
        self.assertEqual(v['effective_floor'],158.4)
        self.assertEqual(r['status'],'budget_conflict')

    def test_weighted_rank_and_eligibility(self):
        r=negotiate([vendor(),vendor(vendor_id='v2',quality='.98',delivery_days=2),
                     vendor(vendor_id='v3',unit_cost_now=1,capacity=9)],200,10)
        self.assertEqual(r['recommended']['vendor_id'],'v2')
        self.assertAlmostEqual(sum(r['weights'].values()),1)
        self.assertAlmostEqual(sum(r['recommended']['weighted_components'].values()),r['recommended']['score'])
        self.assertEqual(r['minimum_budget'],142.23)

    def test_counteroffer_schedule_monotone_and_cent_safe(self):
        r=negotiate([vendor(concession_fraction=0)],142.23,10)
        v=r['vendors'][0]
        bids=[e['amount'] for e in v['rounds'] if e['speaker']=='buyer' and e['action']=='counter']
        self.assertEqual(bids,sorted(bids))
        self.assertTrue(all(Decimal(str(x))<=Decimal('142.23') for x in bids))
        self.assertLessEqual(len(v['rounds']),8)

    def test_rejects_nonfinite_or_inconsistent_inputs(self):
        for kwargs in [{'budget':float('nan'),'quantity':10}, {'budget':100,'quantity':1.5}]:
            with self.assertRaises(ValueError):negotiate([vendor()],**kwargs)
        with self.assertRaises(ValueError):negotiate([vendor(opening_margin='.05')],100,10)
        with self.assertRaises(ValueError):negotiate([vendor(),vendor()],100,10)


if __name__=='__main__':unittest.main()
