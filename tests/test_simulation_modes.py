from pathlib import Path
from contextlib import ExitStack
import tempfile
import sqlite3
import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from procurement import rl_storage,offer_workflow


class SimulationModeTests(unittest.TestCase):
    def test_switching_away_and_back_preserves_valid_marl_navigation(self):
        root=Path(__file__).resolve().parents[1]
        marl_connect=rl_storage.connect;offer_connect=offer_workflow.connect
        native_connect=sqlite3.connect
        with tempfile.TemporaryDirectory() as folder,ExitStack() as cleanup:
            def connect_marl(*a,**k):
                db=marl_connect(Path(folder)/'marl.sqlite3');cleanup.callback(db.close);return db
            def connect_offers(*a,**k):
                db=offer_connect(Path(folder)/'offers.sqlite3');cleanup.callback(db.close);return db
            def thread_safe_test_connection(*a,**k):
                # AppTest executes the app in another thread; allow only test teardown to close its fixtures.
                k['check_same_thread']=False
                return native_connect(*a,**k)
            with (patch('procurement.rl_storage.connect',side_effect=connect_marl),
                  patch('procurement.offer_workflow.connect',side_effect=connect_offers),
                  patch('sqlite3.connect',side_effect=thread_safe_test_connection)):
                app=AppTest.from_file(root/'app.py').run(timeout=45)
                self.assertFalse(app.exception)
                app.button(key='apply_marl_example').click().run(timeout=45)
                app.button(key='FormSubmitter:new_scenario-Buat & jalankan skenario').click().run(timeout=45)
                self.assertFalse(app.exception)
                app.radio(key='simulation_mode').set_value('Simulasi CatBoost').run(timeout=45)
                self.assertFalse(app.exception)
                self.assertGreaterEqual(len(app.dataframe[0].value),5)
                self.assertTrue(all(n.startswith('PT. ') for n in app.dataframe[0].value['Vendor']))
                app.radio(key='simulation_mode').set_value('Simulasi MARL').run(timeout=45)
                self.assertFalse(app.exception)
                self.assertEqual(app.slider[0].value,1)


if __name__=='__main__':unittest.main()
