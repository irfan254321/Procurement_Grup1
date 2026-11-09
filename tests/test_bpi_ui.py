"""Startup behavior for a clone without a local dataset or trained checkpoint."""
from pathlib import Path
import tempfile
import unittest

from streamlit.testing.v1 import AppTest


class BpiUiStartupTests(unittest.TestCase):
    def test_missing_database_has_setup_message_without_creating_empty_database(self):
        with tempfile.TemporaryDirectory() as folder:
            database = Path(folder) / "missing.sqlite3"
            script = ("from procurement.bpi_ui import render_bpi_page\n"
                      f"render_bpi_page(db_path={str(database)!r}, model_dir={folder!r})")
            app = AppTest.from_string(script).run(timeout=20)
            self.assertFalse(app.exception)
            self.assertTrue(any("Database BPI belum tersedia" in w.value for w in app.warning))
            self.assertFalse(database.exists())
            self.assertEqual(len(app.button), 0)

    def test_empty_database_does_not_offer_fake_prediction(self):
        from procurement.bpi import connect
        with tempfile.TemporaryDirectory() as folder:
            database = Path(folder) / "new.sqlite3"
            connect(database).close()
            script = ("from procurement.bpi_ui import render_bpi_page\n"
                      f"render_bpi_page(db_path={str(database)!r}, model_dir={folder!r})")
            app = AppTest.from_string(script).run(timeout=20)
            self.assertFalse(app.exception)
            self.assertTrue(any("belum berisi" in w.value for w in app.warning))
            self.assertEqual(len(app.button), 0)


if __name__ == "__main__":
    unittest.main()
