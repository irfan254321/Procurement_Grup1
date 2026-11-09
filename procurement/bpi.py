"""BPI 2019 ingestion and observed-prefix features, independent of the MARL simulator.

Labels are the next recorded activity, never invented negotiation/payment actions.
Trace attributes are kept for browsing only: their availability at decision time
cannot be established from a final XES snapshot. Only observed events are features.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sqlite3
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "bpi2019.sqlite3"
MODEL_DIR = ROOT / "runs" / "bpi_catboost"
SOURCE = "https://data.4tu.nl/datasets/35ed7122-966a-484e-a0e1-749b64e3366d"
DOWNLOAD = "https://data.4tu.nl/ndownloader/items/35ed7122-966a-484e-a0e1-749b64e3366d/versions/1"
DOI = "10.4121/uuid:d06aff4b-79f0-45e6-8ec8-e19730c248f1"
OFFICIAL_MD5 = "4eb909242351193a61e1c15b9c3cc814"
FEATURE_VERSION = 1
CATEGORICAL = ["last_activity", "previous_activity", "third_last_activity"]
COUNT_ACTIVITIES = ["Create Purchase Order Item", "Record Goods Receipt", "Record Invoice Receipt",
                    "Clear Invoice", "Change Price", "Change Quantity", "Remove Payment Block",
                    "Cancel Goods Receipt", "Cancel Invoice Receipt"]
FEATURES = CATEGORICAL + ["prefix_length", "elapsed_hours", "last_gap_hours", "observed_value",
                         "value_missing", "value_change", "hour", "weekday"] + [
                             f"count_{i}" for i in range(len(COUNT_ACTIVITIES))]


def connect(db_path=DEFAULT_DB):
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript("""
      CREATE TABLE IF NOT EXISTS bpi_dataset (
        id INTEGER PRIMARY KEY CHECK(id=1), source TEXT NOT NULL, doi TEXT NOT NULL,
        license TEXT NOT NULL, sha256 TEXT NOT NULL, md5 TEXT NOT NULL,
        cases INTEGER NOT NULL, events INTEGER NOT NULL,
        imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
      CREATE TABLE IF NOT EXISTS bpi_cases (
        case_id TEXT PRIMARY KEY, document_id TEXT NOT NULL, vendor TEXT,
        first_ts TEXT NOT NULL, last_ts TEXT NOT NULL, event_count INTEGER NOT NULL,
        attributes_json TEXT NOT NULL);
      CREATE INDEX IF NOT EXISTS idx_bpi_document ON bpi_cases(document_id);
      CREATE TABLE IF NOT EXISTS bpi_events (
        case_id TEXT NOT NULL REFERENCES bpi_cases(case_id), event_index INTEGER NOT NULL,
        activity TEXT NOT NULL, timestamp TEXT NOT NULL, value REAL,
        PRIMARY KEY(case_id,event_index));
      CREATE TABLE IF NOT EXISTS bpi_training_runs (
        run_id TEXT PRIMARY KEY, dataset_sha256 TEXT NOT NULL,
        metadata_json TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
      CREATE TABLE IF NOT EXISTS bpi_splits (
        run_id TEXT NOT NULL REFERENCES bpi_training_runs(run_id),
        document_id TEXT NOT NULL, partition TEXT NOT NULL,
        PRIMARY KEY(run_id,document_id));
      CREATE TABLE IF NOT EXISTS bpi_predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL REFERENCES bpi_training_runs(run_id),
        case_id TEXT NOT NULL REFERENCES bpi_cases(case_id), prefix_length INTEGER NOT NULL,
        features_json TEXT NOT NULL, prediction TEXT NOT NULL, probabilities_json TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    """)
    return db


def scalar_attributes(element):
    result = {}
    for child in element:
        if "key" in child.attrib and "value" in child.attrib:
            result[child.attrib["key"]] = child.attrib["value"]
    return result


def import_xes(path, db_path=DEFAULT_DB, verify_official=True):
    """Streaming, transactional and idempotent import. Reject a different dataset.

    XES checksum is computed from uncompressed bytes even when input is a ZIP.
    A corrupt file or checksum mismatch rolls back all imported rows.
    """
    path = Path(path)
    archive = zipfile.ZipFile(path) if zipfile.is_zipfile(path) else None
    if archive:
        entries = [n for n in archive.namelist() if n.lower().endswith(".xes")]
        if len(entries) != 1:
            archive.close()
            raise ValueError("Arsip harus berisi tepat satu berkas XES.")
        opener = lambda: archive.open(entries[0])
    else:
        opener = lambda: path.open("rb")
    db = connect(db_path)
    try:
        sha, md5 = hashlib.sha256(), hashlib.md5()
        with opener() as source:
            for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
                sha.update(chunk)
                md5.update(chunk)
        if verify_official and md5.hexdigest() != OFFICIAL_MD5:
            raise ValueError("Checksum tidak cocok dengan XES resmi BPI Challenge 2019.")
        existing = db.execute("SELECT * FROM bpi_dataset WHERE id=1").fetchone()
        if existing:
            if existing["sha256"] != sha.hexdigest():
                raise ValueError("Database sudah memuat dataset berbeda; gunakan database baru.")
            return dict(existing)
        total_cases = total_events = 0
        with db, opener() as source:
            # Keep the root small; clearing completed traces alone leaves empty nodes behind.
            parser = ET.iterparse(source, events=("start", "end"))
            _, root = next(parser)
            for kind, trace in parser:
                if kind != "end" or trace.tag.rsplit("}", 1)[-1] != "trace":
                    continue
                attrs = scalar_attributes(trace)
                case_id = attrs["concept:name"]
                document = attrs["Purchasing Document"]
                events = []
                for child in trace:
                    if child.tag.rsplit("}", 1)[-1] != "event":
                        continue
                    item = scalar_attributes(child)
                    ts = datetime.fromisoformat(item["time:timestamp"].replace("Z", "+00:00"))
                    # ISO times normalized to UTC so chronological SQL comparisons are sound.
                    from datetime import timezone
                    if ts.tzinfo is None:
                        raise ValueError("Timestamp XES tidak memiliki zona waktu.")
                    ts = ts.astimezone(timezone.utc).isoformat()
                    value = item.get("Cumulative net worth (EUR)")
                    events.append((case_id, len(events), item["concept:name"], ts,
                                   float(value) if value is not None else None))
                if not events:
                    raise ValueError(f"Kasus tanpa event: {case_id}")
                if any(a[3] > b[3] for a, b in zip(events, events[1:])):
                    raise ValueError(f"Timestamp mundur pada kasus {case_id}; urutan tidak diubah diam-diam.")
                db.execute("INSERT INTO bpi_cases VALUES(?,?,?,?,?,?,?)",
                           (case_id, document, attrs.get("Vendor"), events[0][3], events[-1][3],
                            len(events), json.dumps(attrs, ensure_ascii=False)))
                db.executemany("INSERT INTO bpi_events VALUES(?,?,?,?,?)", events)
                total_cases += 1
                total_events += len(events)
                root.clear()
                if total_cases % 25000 == 0:
                    print(f"Imported {total_cases:,} cases / {total_events:,} events", flush=True)
            if not total_cases:
                raise ValueError("Tidak ada trace XES.")
            db.execute("INSERT INTO bpi_dataset(id,source,doi,license,sha256,md5,cases,events) VALUES(1,?,?,?,?,?,?,?)",
                       (SOURCE, DOI, "CC BY 4.0", sha.hexdigest(), md5.hexdigest(), total_cases, total_events))
        return dataset_summary(db)
    finally:
        db.close()
        if archive:
            archive.close()


def dataset_summary(db):
    row = db.execute("SELECT * FROM bpi_dataset WHERE id=1").fetchone()
    return dict(row) if row else {}


def get_case_events(db, case_id):
    return [dict(r) for r in db.execute(
        "SELECT event_index,activity,timestamp,value FROM bpi_events WHERE case_id=? ORDER BY event_index", (case_id,))]


def eligible_prefixes(events):
    # Exclude ambiguous next-event order at tied timestamps. No artificial END label.
    return [k for k in range(1, len(events)) if events[k]["timestamp"] > events[k - 1]["timestamp"]]


def prefix_features(events, prefix_length):
    if not 1 <= prefix_length <= len(events):
        raise ValueError("Panjang prefix di luar jumlah event yang diamati.")
    past = events[:prefix_length]
    last = past[-1]
    end = datetime.fromisoformat(last["timestamp"])
    start = datetime.fromisoformat(past[0]["timestamp"])
    previous = datetime.fromisoformat(past[-2]["timestamp"]) if len(past) > 1 else end
    counts = Counter(e["activity"] for e in past)
    value = last["value"]
    previous_value = past[-2]["value"] if len(past) > 1 else value
    features = {
        "last_activity": last["activity"],
        "previous_activity": past[-2]["activity"] if len(past) > 1 else "__START__",
        "third_last_activity": past[-3]["activity"] if len(past) > 2 else "__START__",
        "prefix_length": prefix_length,
        "elapsed_hours": (end - start).total_seconds() / 3600,
        "last_gap_hours": (end - previous).total_seconds() / 3600,
        "observed_value": value if value is not None else 0.0,
        "value_missing": int(value is None),
        "value_change": value - previous_value if value is not None and previous_value is not None else 0.0,
        "hour": end.hour, "weekday": end.weekday(),
    }
    features.update({f"count_{i}": counts[name] for i, name in enumerate(COUNT_ACTIVITIES)})
    return features


def list_test_cases(db, limit=100):
    run = db.execute("SELECT run_id FROM bpi_training_runs ORDER BY created_at DESC, rowid DESC LIMIT 1").fetchone()
    if not run:
        return []
    return [dict(r) for r in db.execute("""
      SELECT c.case_id,c.document_id,c.vendor,c.event_count FROM bpi_cases c
      JOIN bpi_splits s ON s.document_id=c.document_id
      WHERE s.run_id=? AND s.partition='test' AND c.event_count>1
      ORDER BY c.case_id LIMIT ?""", (run[0], limit))]


def register_model(db, model_dir=MODEL_DIR):
    """Restore the audit registry after cloning GitHub and importing the raw data.

    Model manifests travel with the checkpoint; the large database does not.
    Training is not repeated and no model artifact is unpickled.
    """
    import csv
    model_dir = Path(model_dir)
    metadata_path = model_dir / "metrics.json"
    if not metadata_path.exists():
        return False
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata["dataset_sha256"] != dataset_summary(db).get("sha256"):
        raise ValueError("Model tidak dibuat dari dataset yang sedang diimpor.")
    if metadata["feature_version"] != FEATURE_VERSION:
        raise ValueError("Versi fitur model tidak cocok.")
    if hashlib.sha256((model_dir / "model.cbm").read_bytes()).hexdigest() != metadata["model_sha256"]:
        raise ValueError("Checksum checkpoint tidak cocok.")
    run_id = metadata["run_id"]
    if Path(run_id).name != run_id or run_id in (".", ".."):
        raise ValueError("ID training tidak valid.")
    registered = db.execute("SELECT metadata_json FROM bpi_training_runs WHERE run_id=?", (run_id,)).fetchone()
    if registered:
        if json.loads(registered[0]) != metadata:
            raise ValueError("ID training sudah terdaftar dengan metadata berbeda.")
        return True
    documents = {}
    for group in ("train", "validation", "test"):
        with (model_dir / run_id / f"{group}_manifest.csv").open(encoding="utf-8", newline="") as source:
            for row in csv.DictReader(source):
                key = row["document_id"]
                if documents.setdefault(key, group) != group:
                    raise ValueError("Manifest mengandung dokumen yang melintasi partisi.")
    with db:
        db.execute("INSERT INTO bpi_training_runs(run_id,dataset_sha256,metadata_json) VALUES(?,?,?)",
                   (run_id, metadata["dataset_sha256"], json.dumps(metadata, ensure_ascii=False)))
        db.executemany("INSERT INTO bpi_splits VALUES(?,?,?)",
                       [(run_id, document, group) for document, group in documents.items()])
    return True


def predict_next(case_id, prefix_length, db_path=DEFAULT_DB, model_dir=MODEL_DIR, persist=True):
    from catboost import CatBoostClassifier
    import pandas as pd
    model_dir = Path(model_dir)
    metadata = json.loads((model_dir / "metrics.json").read_text(encoding="utf-8"))
    if metadata["feature_version"] != FEATURE_VERSION:
        raise ValueError("Versi fitur model tidak cocok; latih ulang.")
    model_path = model_dir / "model.cbm"
    if hashlib.sha256(model_path.read_bytes()).hexdigest() != metadata["model_sha256"]:
        raise ValueError("Checksum model tidak cocok dengan metadata training.")
    db = connect(db_path)
    try:
        register_model(db, model_dir)
        if dataset_summary(db).get("sha256") != metadata["dataset_sha256"]:
            raise ValueError("Dataset model berbeda dari database aktif.")
        events = get_case_events(db, case_id)
        features = prefix_features(events, prefix_length)
        model = CatBoostClassifier()
        model.load_model(str(model_path))
        scores = model.predict_proba(pd.DataFrame([features], columns=FEATURES))[0]
        ranking = sorted([{"activity": str(label), "probability": float(p)}
                          for label, p in zip(model.classes_, scores)], key=lambda r: -r["probability"])
        prediction_id = None
        if persist:
            with db:
                cur = db.execute("""INSERT INTO bpi_predictions
                  (run_id,case_id,prefix_length,features_json,prediction,probabilities_json) VALUES(?,?,?,?,?,?)""",
                  (metadata["run_id"], case_id, prefix_length, json.dumps(features), ranking[0]["activity"], json.dumps(ranking)))
                prediction_id = cur.lastrowid
        return {"prediction": ranking[0]["activity"], "probabilities": ranking,
                "actual_next_activity": events[prefix_length]["activity"] if prefix_length < len(events) else None,
                "run_id": metadata["run_id"], "prediction_id": prediction_id}
    finally:
        db.close()
