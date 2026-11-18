"""Set up and run a local BIZ District installation."""

import os
from pathlib import Path
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parent
ENVIRONMENT = ROOT / ".venv"
DATA = ROOT / "data"


def run():
    if sys.version_info[:2] != (3, 14):
        raise SystemExit("Jalankan installer dengan Python 3.14 (64-bit).")

    if not (DATA / "spend_analysis_dataset.csv").is_file():
        raise SystemExit("CSV katalog belum tersedia. Lihat bagian Dataset di README.md.")

    python = ENVIRONMENT / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.is_file():
        print("Membuat lingkungan Python lokal...", flush=True)
        venv.create(ENVIRONMENT, with_pip=True)

    print("Memeriksa dependensi...", flush=True)
    subprocess.run(
        [str(python), "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")],
        check=True, cwd=ROOT,
    )
    print("Memeriksa model agen...", flush=True)
    subprocess.run([str(python), "train.py", "--ensure"], check=True, cwd=ROOT)

    print("Memeriksa dataset dan model pemasok...", flush=True)
    subprocess.run([str(python), "download_supplier_data.py"], check=True, cwd=ROOT)
    subprocess.run([str(python), "supplier_training.py", "--ensure"], check=True, cwd=ROOT)

    subprocess.run([str(python), "server.py"], check=True, cwd=ROOT)


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        pass
