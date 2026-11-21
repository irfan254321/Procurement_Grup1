import csv

from paths import PROCUREMENT_SOURCE

RETIRED_SUPPLIER = "OfficeSupplies Co."


def read_purchases():
    with PROCUREMENT_SOURCE.open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    if len({row["TransactionID"] for row in rows}) != len(rows):
        raise ValueError("TransactionID harus unik.")
    return rows
