"""Regression tests for authentic-event ingestion and prefix-only prediction inputs."""
from __future__ import annotations

from copy import deepcopy
from contextlib import closing
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from procurement.bpi import (
    CATEGORICAL, FEATURES, FEATURE_VERSION, connect, dataset_summary, eligible_prefixes, get_case_events,
    import_xes, predict_next, prefix_features, register_model,
)
from procurement.bpi_training import build_samples, split_documents


def trace_xml(case_id, document_id, events, vendor="vendor_001"):
    trace = ET.Element("trace")
    for key, value in {
        "concept:name": case_id, "Purchasing Document": document_id,
        "Vendor": vendor, "Name": vendor, "Item Category": "3-way match",
    }.items():
        ET.SubElement(trace, "string", key=key, value=str(value))
    for activity, timestamp, value in events:
        event = ET.SubElement(trace, "event")
        ET.SubElement(event, "string", key="concept:name", value=activity)
        ET.SubElement(event, "date", key="time:timestamp", value=timestamp)
        ET.SubElement(event, "float", key="Cumulative net worth (EUR)", value=str(value))
        ET.SubElement(event, "string", key="org:resource", value="user_001")
    return ET.tostring(trace, encoding="unicode")


class BpiIngestionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db_path = self.root / "data.sqlite3"
        self.first_trace = trace_xml("PO001_01", "PO001", [
            ("Create Purchase Order Item", "2018-01-01T01:00:00+01:00", 100),
            ("Change Price", "2018-01-02T00:00:00Z", 95),
            ("Record Goods Receipt", "2018-01-03T00:00:00Z", 95),
        ])
        self.second_trace = trace_xml("PO001_02", "PO001", [
            ("Create Purchase Order Item", "2018-01-01T00:00:00Z", 40),
            ("Record Invoice Receipt", "2018-01-04T00:00:00Z", 40),
        ])
        self.xes = self.root / "fixture.xes"
        self.xes.write_text("<log>" + self.first_trace + self.second_trace + "</log>", encoding="utf-8")

    def test_import_is_idempotent_and_preserves_real_labels_and_po_group(self):
        first = import_xes(self.xes, self.db_path, verify_official=False)
        second = import_xes(self.xes, self.db_path, verify_official=False)
        self.assertEqual(first, second)
        self.assertEqual((first["cases"], first["events"]), (2, 5))
        self.assertEqual(first["sha256"], hashlib.sha256(self.xes.read_bytes()).hexdigest())
        with closing(connect(self.db_path)) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM bpi_cases").fetchone()[0], 2)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM bpi_events").fetchone()[0], 5)
            self.assertEqual(db.execute("SELECT COUNT(DISTINCT document_id) FROM bpi_cases").fetchone()[0], 1)
            events = get_case_events(db, "PO001_01")
            self.assertEqual([e["activity"] for e in events],
                             ["Create Purchase Order Item", "Change Price", "Record Goods Receipt"])
            self.assertEqual(events[0]["timestamp"], "2018-01-01T00:00:00+00:00")
            self.assertEqual([e["event_index"] for e in events], [0, 1, 2])
            self.assertEqual(dataset_summary(db)["sha256"], first["sha256"])

    def test_zip_and_raw_xes_have_same_content_identity(self):
        expected = import_xes(self.xes, self.db_path, verify_official=False)
        archive = self.root / "fixture.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
            zipped.write(self.xes, "dataset/fixture.xes")
        actual = import_xes(archive, self.db_path, verify_official=False)
        self.assertEqual(actual, expected)

    def test_malformed_xml_rolls_back_previously_imported_traces(self):
        malformed = self.root / "malformed.xes"
        malformed.write_text("<log>" + self.first_trace + "<trace><event></log>", encoding="utf-8")
        with self.assertRaises(ET.ParseError):
            import_xes(malformed, self.db_path, verify_official=False)
        with closing(connect(self.db_path)) as db:
            for table in ("bpi_dataset", "bpi_cases", "bpi_events"):
                self.assertEqual(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 0)
        # A failed import must not prevent a subsequent valid transaction.
        result = import_xes(self.xes, self.db_path, verify_official=False)
        self.assertEqual(result["cases"], 2)

    def test_default_import_rejects_non_official_checksum(self):
        with self.assertRaisesRegex(ValueError, "Checksum"):
            import_xes(self.xes, self.db_path)
        with closing(connect(self.db_path)) as db:
            self.assertFalse(dataset_summary(db))
            self.assertEqual(db.execute("SELECT COUNT(*) FROM bpi_cases").fetchone()[0], 0)

    def test_different_dataset_cannot_replace_existing_data(self):
        expected = import_xes(self.xes, self.db_path, verify_official=False)
        alternate = self.root / "different.xes"
        alternate.write_text("<log>" + self.first_trace + "</log>", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "dataset berbeda"):
            import_xes(alternate, self.db_path, verify_official=False)
        with closing(connect(self.db_path)) as db:
            self.assertEqual(dataset_summary(db), expected)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM bpi_events").fetchone()[0], 5)

    def test_samples_use_actual_next_labels_and_keep_unseen_test_classes(self):
        traces = [
            trace_xml("TRAIN_01", "TRAIN", [
                ("Create Purchase Order Item", "2018-01-01T00:00:00Z", 100),
                ("Change Price", "2018-01-02T00:00:00Z", 90),
            ]),
            trace_xml("TRAIN_02", "TRAIN", [
                ("Create Purchase Order Item", "2018-01-01T00:00:00Z", 80),
                ("Change Quantity", "2018-01-02T00:00:00Z", 70),
            ]),
            trace_xml("VAL_01", "VAL", [
                ("Create Purchase Order Item", "2018-01-03T00:00:00Z", 100),
                ("Change Price", "2018-01-04T00:00:00Z", 90),
            ]),
            trace_xml("TEST_01", "TEST", [
                ("Create Purchase Order Item", "2018-01-05T00:00:00Z", 100),
                ("SRM: Complete", "2018-01-05T00:00:00Z", 100),
                ("Previously Unseen Test Activity", "2018-01-06T00:00:00Z", 80),
            ]),
        ]
        self.xes.write_text("<log>" + "".join(traces) + "</log>", encoding="utf-8")
        import_xes(self.xes, self.db_path, verify_official=False)
        mapping = {"TRAIN": "train", "VAL": "validation", "TEST": "test"}
        with closing(connect(self.db_path)) as db:
            frames, selected, stats = build_samples(db, mapping, seed=42,
                train_documents=1, validation_documents=1, test_documents=1)
            self.assertEqual(selected, mapping)
            self.assertEqual(stats["ties_excluded"], 1)
            self.assertEqual(len(frames["train"]), 2)
            self.assertEqual(frames["test"]["label"].tolist(), ["Previously Unseen Test Activity"])
            self.assertNotIn("Previously Unseen Test Activity", set(frames["train"]["label"]))
            for group, frame in frames.items():
                self.assertTrue(all(mapping[document] == group for document in frame["document_id"]))
                for _, row in frame.iterrows():
                    events = get_case_events(db, row["case_id"])
                    length = int(row["prefix_length_audit"])
                    self.assertEqual(row["label"], events[length]["activity"])
                    self.assertEqual(row["target_timestamp"], events[length]["timestamp"])
                    self.assertEqual(row[FEATURES].to_dict(), prefix_features(events, length))

    def registration_artifacts(self):
        # Registration validates bytes/digests and manifests without deserializing a model.
        dataset = import_xes(self.xes, self.db_path, verify_official=False)
        model_dir = self.root / "registered_model"
        archive = model_dir / "fixture-register"
        archive.mkdir(parents=True)
        model_bytes = b"checkpoint identity fixture; not loaded by registration"
        (model_dir / "model.cbm").write_bytes(model_bytes)
        metadata = {
            "run_id": archive.name, "dataset_sha256": dataset["sha256"],
            "feature_version": FEATURE_VERSION,
            "model_sha256": hashlib.sha256(model_bytes).hexdigest(),
        }
        (model_dir / "metrics.json").write_text(json.dumps(metadata), encoding="utf-8")
        for group in ("train", "validation", "test"):
            rows = "case_id,document_id\n"
            if group == "test":
                rows += "PO001_01,PO001\nPO001_02,PO001\n"
            (archive / f"{group}_manifest.csv").write_text(rows, encoding="utf-8")
        return model_dir, metadata

    def test_registration_restores_cloned_model_audit_without_retraining(self):
        model_dir, metadata = self.registration_artifacts()
        with closing(connect(self.db_path)) as db:
            self.assertTrue(register_model(db, model_dir))
            self.assertTrue(register_model(db, model_dir))
            self.assertEqual(db.execute("SELECT COUNT(*) FROM bpi_training_runs").fetchone()[0], 1)
            rows = db.execute("SELECT document_id,partition FROM bpi_splits").fetchall()
            self.assertEqual([tuple(row) for row in rows], [("PO001", "test")])
            restored = db.execute("SELECT metadata_json FROM bpi_training_runs").fetchone()[0]
            self.assertEqual(json.loads(restored), metadata)

    def test_registration_rejects_tampered_checkpoint(self):
        model_dir, _ = self.registration_artifacts()
        (model_dir / "model.cbm").write_bytes(b"different checkpoint")
        with closing(connect(self.db_path)) as db:
            with self.assertRaisesRegex(ValueError, "Checksum checkpoint"):
                register_model(db, model_dir)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM bpi_training_runs").fetchone()[0], 0)

    def test_registration_rejects_document_overlap_before_inserting_audit(self):
        model_dir, metadata = self.registration_artifacts()
        (model_dir / metadata["run_id"] / "train_manifest.csv").write_text(
            "case_id,document_id\nPO001_01,PO001\n", encoding="utf-8")
        with closing(connect(self.db_path)) as db:
            with self.assertRaisesRegex(ValueError, "melintasi partisi"):
                register_model(db, model_dir)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM bpi_training_runs").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM bpi_splits").fetchone()[0], 0)

    @unittest.skipUnless(importlib.util.find_spec("catboost"), "CatBoost is required for artifact parity")
    def test_saved_catboost_prediction_matches_reload_and_is_audited(self):
        from catboost import CatBoostClassifier
        import pandas as pd

        dataset = import_xes(self.xes, self.db_path, verify_official=False)
        with closing(connect(self.db_path)) as db:
            events = get_case_events(db, "PO001_01")
        training = pd.DataFrame([
            prefix_features(events, 1), prefix_features(events, 2),
        ] * 3, columns=FEATURES)
        model = CatBoostClassifier(iterations=3, depth=2, random_seed=7, thread_count=1,
                                   cat_features=CATEGORICAL, allow_writing_files=False, verbose=False)
        model.fit(training, ["Change Price", "Record Goods Receipt"] * 3)
        model_dir = self.root / "model"
        model_dir.mkdir()
        model_path = model_dir / "model.cbm"
        model.save_model(str(model_path))
        metadata = {
            "run_id": "fixture-run", "dataset_sha256": dataset["sha256"],
            "feature_version": FEATURE_VERSION,
            "model_sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
        }
        (model_dir / "metrics.json").write_text(json.dumps(metadata), encoding="utf-8")
        with closing(connect(self.db_path)) as db, db:
            db.execute("INSERT INTO bpi_training_runs(run_id,dataset_sha256,metadata_json) VALUES(?,?,?)",
                       (metadata["run_id"], dataset["sha256"], json.dumps(metadata)))
        expected = dict(zip(model.classes_, model.predict_proba(training.iloc[[1]])[0]))
        result = predict_next("PO001_01", 2, self.db_path, model_dir)
        self.assertEqual(result["actual_next_activity"], "Record Goods Receipt")
        self.assertEqual(result["prediction"], max(expected, key=expected.get))
        for item in result["probabilities"]:
            self.assertAlmostEqual(item["probability"], expected[item["activity"]], places=12)
        with closing(connect(self.db_path)) as db:
            record = db.execute("SELECT * FROM bpi_predictions WHERE id=?", (result["prediction_id"],)).fetchone()
            self.assertEqual(record["case_id"], "PO001_01")
            self.assertEqual(record["run_id"], "fixture-run")
            self.assertEqual(json.loads(record["features_json"]), prefix_features(events, 2))


class BpiPrefixTests(unittest.TestCase):
    def events(self):
        return [
            {"activity": "Create Purchase Order Item", "timestamp": "2018-01-01T00:00:00+00:00", "value": 100.0},
            {"activity": "Change Price", "timestamp": "2018-01-02T00:00:00+00:00", "value": 95.0},
            {"activity": "Record Goods Receipt", "timestamp": "2018-01-03T00:00:00+00:00", "value": 95.0},
            {"activity": "Clear Invoice", "timestamp": "2018-01-04T00:00:00+00:00", "value": 95.0},
        ]

    def test_mutating_future_cannot_change_prediction_features(self):
        events = self.events()
        expected = prefix_features(events, 2)
        changed = deepcopy(events)
        changed[2:] = [{"activity": "FUTURE_SECRET", "timestamp": "2099-12-31T00:00:00+00:00", "value": 999999}]
        self.assertEqual(prefix_features(changed, 2), expected)
        self.assertEqual(prefix_features(events[:2], 2), expected)
        self.assertEqual(expected["value_change"], -5.0)

    def test_identity_and_snapshot_attributes_are_not_features(self):
        events = self.events()
        original = prefix_features(events, 2)
        for event in events:
            event.update({"case_id": "CASE_SECRET", "document_id": "DOC_SECRET", "Vendor": "VENDOR_SECRET",
                          "Name": "NAME_SECRET", "Source": "SOURCE_SECRET", "User": "USER_SECRET",
                          "org:resource": "RESOURCE_SECRET", "Item Category": "FINAL_SNAPSHOT_SECRET"})
        actual = prefix_features(events, 2)
        self.assertEqual(actual, original)
        self.assertEqual(set(actual), set(FEATURES))
        self.assertFalse(any("SECRET" in str(value) for value in actual.values()))

    def test_tied_next_event_is_excluded_and_no_end_label_is_created(self):
        events = self.events()
        events[1]["timestamp"] = events[0]["timestamp"]
        self.assertEqual(eligible_prefixes(events), [2, 3])
        self.assertEqual(eligible_prefixes(events[:1]), [])
        self.assertNotIn(len(events), eligible_prefixes(events))
        for length in eligible_prefixes(events):
            self.assertGreater(events[length]["timestamp"], events[length - 1]["timestamp"])

    def test_invalid_prefix_length_is_rejected(self):
        events = self.events()
        for length in (0, -1, len(events) + 1):
            with self.subTest(length=length), self.assertRaises(ValueError):
                prefix_features(events, length)


class BpiSplitTests(unittest.TestCase):
    def test_document_items_stay_together_and_boundary_spans_are_excluded(self):
        with tempfile.TemporaryDirectory() as directory, closing(connect(Path(directory) / "split.sqlite3")) as db:
            start = datetime(2018, 1, 1, tzinfo=timezone.utc)
            # Two items share each document. Long-running second items make
            # PO15 and PO19 cross validation/test cutoffs respectively.
            with db:
                for index in range(24):
                    document = f"PO{index:02d}"
                    first = start + timedelta(days=index)
                    for item in (1, 2):
                        end = first + timedelta(hours=item)
                        if item == 2 and index in (15, 19):
                            end = first + timedelta(days=3)
                        db.execute("INSERT INTO bpi_cases VALUES(?,?,?,?,?,?,?)", (
                            f"{document}_{item}", document, "vendor_1",
                            first.isoformat(), end.isoformat(), 2, "{}",
                        ))
            mapping, details = split_documents(db)
            self.assertNotIn("PO15", mapping)
            self.assertNotIn("PO19", mapping)
            self.assertEqual(details["documents_excluded_cross_boundary"], 2)
            self.assertEqual(details["documents_eligible"], {"train": 15, "validation": 3, "test": 4})
            self.assertEqual(details["cutoff_validation"], (start + timedelta(days=16)).isoformat())
            self.assertEqual(details["cutoff_test"], (start + timedelta(days=20)).isoformat())
            for row in db.execute("SELECT document_id,first_ts,last_ts FROM bpi_cases"):
                partition = mapping.get(row["document_id"])
                if partition == "train":
                    self.assertLess(row["last_ts"], details["cutoff_validation"])
                elif partition == "validation":
                    self.assertGreaterEqual(row["first_ts"], details["cutoff_validation"])
                    self.assertLess(row["last_ts"], details["cutoff_test"])
                elif partition == "test":
                    self.assertGreaterEqual(row["first_ts"], details["cutoff_test"])

    def test_too_few_documents_cannot_produce_a_training_split(self):
        with tempfile.TemporaryDirectory() as directory, closing(connect(Path(directory) / "split.sqlite3")) as db:
            with self.assertRaisesRegex(ValueError, "20 purchase documents"):
                split_documents(db)


if __name__ == "__main__":
    unittest.main()
