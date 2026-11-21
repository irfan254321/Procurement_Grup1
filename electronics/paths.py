from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
WEB = ROOT / "web"
PROCUREMENT_SOURCE = DATA / "spend_analysis_dataset.csv"
SUPPLIER_DATA = DATA / "supplier"
SUPPLIER_SOURCE = SUPPLIER_DATA / "SCMS_Delivery_History_Dataset.csv"
WORLD_DATABASE = DATA / "electronics.sqlite3"
