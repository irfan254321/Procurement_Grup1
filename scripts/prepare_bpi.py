"""Download official BPI 2019 archive and import a reproducible local database."""
import argparse
import json
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from procurement.bpi import DEFAULT_DB, DOWNLOAD, connect, import_xes, register_model


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="Existing official XES or ZIP; otherwise download from 4TU")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    source = args.input or ROOT / "data" / "raw" / "bpi2019.zip"
    if not source.exists():
        if args.input:
            parser.error(f"Berkas tidak ditemukan: {source}")
        source.parent.mkdir(parents=True, exist_ok=True)
        temporary = source.with_suffix(".download")
        print("Downloading official BPI 2019 (approximately 729 MB)...", flush=True)
        request = urllib.request.Request(DOWNLOAD, headers={"User-Agent": "Procurement-BPI-Research/1.0"})
        try:
            with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as out:
                while chunk := response.read(4 * 1024 * 1024):
                    out.write(chunk)
            temporary.replace(source)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
    print(json.dumps(import_xes(source, args.db), indent=2), flush=True)
    db = connect(args.db)
    try:
        print("Existing model registered:", register_model(db), flush=True)
    finally:
        db.close()


if __name__ == "__main__":
    main()
