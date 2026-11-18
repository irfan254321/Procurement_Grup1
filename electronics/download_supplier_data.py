"""Download the one pinned public Kaggle supplier dataset without an account."""
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from urllib.request import Request, urlopen
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parent
DESTINATION = ROOT / "data" / "supplier" / "SCMS_Delivery_History_Dataset.csv"
URL = "https://www.kaggle.com/api/v1/datasets/download/divyeshardeshana/supply-chain-shipment-pricing-data"
EXPECTED_SHA256 = "918b992dd3e8d4b64d2a727b2c4ea607603d0c58f19484e73f7b78528c6a8673"


def download():
    if DESTINATION.is_file() and sha256(DESTINATION.read_bytes()).hexdigest() == EXPECTED_SHA256:
        print("Dataset pemasok sudah tersedia dan checksum sesuai.")
        return
    request = Request(URL, headers={"User-Agent": "BIZ-District-Dataset-Downloader/1.0"})
    with urlopen(request, timeout=90) as response:
        archive = response.read(20_000_001)
    if len(archive) > 20_000_000:
        raise ValueError("Arsip melebihi batas unduhan yang diharapkan.")
    with ZipFile(BytesIO(archive)) as source:
        # Read one expected member directly; never extract arbitrary archive paths.
        member = "SCMS_Delivery_History_Dataset.csv"
        entry = source.getinfo(member)
        if entry.file_size > 10_000_000:
            raise ValueError("CSV melebihi ukuran yang diharapkan.")
        content = source.read(member)
    if sha256(content).hexdigest() != EXPECTED_SHA256:
        raise ValueError("Checksum sumber berubah; tinjau versi dataset sebelum mengganti sumber lokal.")
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    DESTINATION.write_bytes(content)
    print(f"Dataset Kaggle tersimpan: {DESTINATION}")


if __name__ == "__main__":
    download()
