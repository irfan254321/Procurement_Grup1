"""CatBoost next-activity learning with document-grouped chronological evaluation."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import uuid

from .bpi import (CATEGORICAL, DEFAULT_DB, FEATURES, FEATURE_VERSION, MODEL_DIR,
                  connect, dataset_summary, eligible_prefixes, get_case_events, prefix_features)


def split_documents(db):
    documents = [dict(r) for r in db.execute("""SELECT document_id,MIN(first_ts) AS start,
                     MAX(last_ts) AS end FROM bpi_cases GROUP BY document_id ORDER BY start,document_id""")]
    if len(documents) < 20:
        raise ValueError("Minimal 20 purchase documents untuk split waktu yang bermakna.")
    cutoff_validation = documents[int(len(documents) * .70)]["start"]
    cutoff_test = documents[int(len(documents) * .85)]["start"]
    mapping, excluded = {}, 0
    for row in documents:
        if row["end"] < cutoff_validation:
            group = "train"
        elif row["start"] >= cutoff_validation and row["end"] < cutoff_test:
            group = "validation"
        elif row["start"] >= cutoff_test:
            group = "test"
        else:
            excluded += 1
            continue
        mapping[row["document_id"]] = group
    return mapping, {
        "method": "Chronological by Purchasing Document; boundary-spanning documents excluded",
        "cutoff_validation": cutoff_validation, "cutoff_test": cutoff_test,
        "documents_total": len(documents), "documents_excluded_cross_boundary": excluded,
        "documents_eligible": dict(Counter(mapping.values())),
    }


def build_samples(db, mapping, seed=42, train_documents=1500, validation_documents=1000,
                  test_documents=1000, max_prefixes_per_case=30):
    import pandas as pd
    if min(train_documents, validation_documents, test_documents, max_prefixes_per_case) < 1:
        raise ValueError("Batas sampel harus positif.")
    rng = random.Random(seed)
    selected = {}
    for group, limit in [("train", train_documents), ("validation", validation_documents), ("test", test_documents)]:
        keys = sorted(k for k, v in mapping.items() if v == group)
        if not keys:
            raise ValueError(f"Tidak ada dokumen untuk {group}.")
        for key in rng.sample(keys, min(limit, len(keys))):
            selected[key] = group
    rows = defaultdict(list)
    stats = {"documents_selected": dict(Counter(selected.values())), "ties_excluded": 0,
             "prefixes_available": 0, "prefixes_sampled_out": 0}
    for case in db.execute("SELECT case_id,document_id FROM bpi_cases ORDER BY case_id"):
        group = selected.get(case["document_id"])
        if group is None:
            continue
        events = get_case_events(db, case["case_id"])
        prefixes = eligible_prefixes(events)
        stats["ties_excluded"] += len(events) - 1 - len(prefixes)
        stats["prefixes_available"] += len(prefixes)
        if len(prefixes) > max_prefixes_per_case:
            stats["prefixes_sampled_out"] += len(prefixes) - max_prefixes_per_case
            prefixes = sorted(rng.sample(prefixes, max_prefixes_per_case))
        for length in prefixes:
            rows[group].append({**prefix_features(events, length),
                                "label": events[length]["activity"],
                                "case_id": case["case_id"], "document_id": case["document_id"],
                                "prefix_length_audit": length,
                                "target_timestamp": events[length]["timestamp"]})
    if any(not rows[g] for g in ("train", "validation", "test")):
        raise ValueError("Salah satu partisi tidak memiliki pasangan event berurutan yang valid.")
    return {g: pd.DataFrame(rows[g]) for g in ("train", "validation", "test")}, selected, stats


def train(db_path=DEFAULT_DB, model_dir=MODEL_DIR, seed=42, iterations=120,
          train_documents=1500, validation_documents=1000, test_documents=1000,
          max_prefixes_per_case=30, threads=4):
    import catboost
    from catboost import CatBoostClassifier
    import numpy as np
    import sklearn
    from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score

    db = connect(db_path)
    try:
        dataset = dataset_summary(db)
        if not dataset:
            raise ValueError("Impor BPI terlebih dahulu: python scripts/prepare_bpi.py")
        mapping, split = split_documents(db)
        frames, selected, sampling = build_samples(
            db, mapping, seed, train_documents, validation_documents, test_documents, max_prefixes_per_case)
        training, validation, test = (frames[g] for g in ("train", "validation", "test"))
        classes = set(training["label"])
        if len(classes) < 2:
            raise ValueError("Data train hanya memiliki satu kelas.")
        known_validation = validation[validation["label"].isin(classes)]
        if known_validation.empty:
            raise ValueError("Tidak ada kelas validasi yang pernah diamati saat training.")
        print("Training samples:", {g: len(f) for g, f in frames.items()}, flush=True)
        model = CatBoostClassifier(iterations=iterations, depth=5, learning_rate=.08,
                                   loss_function="MultiClass", random_seed=seed,
                                   thread_count=threads, allow_writing_files=False,
                                   cat_features=CATEGORICAL, verbose=25)
        model.fit(training[FEATURES], training["label"],
                  eval_set=(known_validation[FEATURES], known_validation["label"]),
                  early_stopping_rounds=30, use_best_model=True)
        prediction = np.asarray(model.predict(test[FEATURES])).reshape(-1)
        probabilities = model.predict_proba(test[FEATURES])
        top3 = np.asarray(model.classes_)[np.argsort(probabilities, axis=1)[:, -3:]]
        truth = test["label"].to_numpy()
        majority = training["label"].value_counts().index[0]
        conditional = training.groupby("last_activity")["label"].agg(lambda v: v.value_counts().index[0]).to_dict()
        baseline = [conditional.get(a, majority) for a in test["last_activity"]]
        labels = sorted(set(truth) | set(prediction))
        metrics = {
            "accuracy": float(accuracy_score(truth, prediction)),
            "macro_f1": float(f1_score(truth, prediction, average="macro", zero_division=0)),
            "weighted_f1": float(f1_score(truth, prediction, average="weighted", zero_division=0)),
            "top3_accuracy": float(np.mean([y in p for y, p in zip(truth, top3)])),
            "baseline_accuracy": float(np.mean(truth == majority)),
            "conditional_baseline_accuracy": float(accuracy_score(truth, baseline)),
            "conditional_baseline_macro_f1": float(f1_score(truth, baseline, average="macro", zero_division=0)),
            "test_samples": len(test),
            "unseen_test_labels": int(sum(y not in classes for y in truth)),
            "classification_report": classification_report(truth, prediction, zero_division=0, output_dict=True),
            "confusion_labels": labels,
            "confusion_matrix": confusion_matrix(truth, prediction, labels=labels).tolist(),
        }
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
        destination = Path(model_dir)
        archive = destination / run_id
        archive.mkdir(parents=True, exist_ok=False)
        model.save_model(str(archive / "model.cbm"))
        model_hash = hashlib.sha256((archive / "model.cbm").read_bytes()).hexdigest()
        metadata = {
            "run_id": run_id, "task": "Next recorded activity from observed event prefix",
            "feature_version": FEATURE_VERSION, "features": FEATURES, "categorical_features": CATEGORICAL,
            "source": dataset["source"], "doi": dataset["doi"], "license": dataset["license"],
            "dataset_sha256": dataset["sha256"], "model_sha256": model_hash,
            "algorithm": "CatBoostClassifier", "seed": seed,
            "versions": {"catboost": catboost.__version__, "scikit_learn": sklearn.__version__},
            "parameters": {"iterations_requested": iterations, "trees_trained": model.tree_count_,
                           "depth": 5, "learning_rate": .08, "threads": threads,
                           "max_prefixes_per_case": max_prefixes_per_case},
            "split": split, "sampling": sampling,
            "samples": {g: len(f) for g, f in frames.items()},
            "validation_unseen_labels_excluded_from_early_stopping": len(validation) - len(known_validation),
            "metrics": metrics,
            "limitations": [
                "Satu model aktivitas berikutnya; bukan empat policy IRE/VMI/DA/SLM yang telah dilatih.",
                "Meniru aktivitas historis; tidak membuktikan tindakan paling optimal atau efek kausal.",
                "Pilihan kandidat vendor, tawar-menawar, pembagian pesanan, dan termin tidak diberi label oleh BPI.",
                "Snapshot vendor/kategori kasus tidak dipakai sebagai fitur; hanya event yang sudah diamati.",
                "Pasangan timestamp sama dikeluarkan; urutan historis yang tersisa mengikuti XES.",
                "Tidak membuat label END; akhir trace dapat berarti periode observasi terpotong.",
                "Evaluasi memakai sampel dokumen dengan seed tetap; seluruh data mentah tetap di database.",
                "Dokumen yang melintasi cutoff dikeluarkan; evaluasi dapat kurang mewakili kasus panjang/kompleks.",
                "Kelas langka/tidak dikenal tetap dihitung pada test; lihat macro-F1 dan recall per kelas.",
                "Nilai EUR dianonimkan dan tidak sama dengan rupiah atau harga riil.",
                "Baru CatBoost diuji; belum ada perbandingan Decision Tree atau SVM.",
            ],
        }
        for group, frame in frames.items():
            frame[["case_id", "document_id", "prefix_length_audit", "target_timestamp", "label"]].to_csv(
                archive / f"{group}_manifest.csv", index=False)
        encoded = json.dumps(metadata, indent=2, ensure_ascii=False)
        (archive / "metrics.json").write_text(encoded, encoding="utf-8")
        with db:
            db.execute("INSERT INTO bpi_training_runs(run_id,dataset_sha256,metadata_json) VALUES(?,?,?)",
                       (run_id, dataset["sha256"], encoded))
            db.executemany("INSERT INTO bpi_splits VALUES(?,?,?)",
                           [(run_id, key, group) for key, group in selected.items()])
        # Preserve immutable per-run artifacts; active files are published only after training succeeds.
        import shutil
        shutil.copyfile(archive / "model.cbm", destination / "model.cbm.tmp")
        (destination / "model.cbm.tmp").replace(destination / "model.cbm")
        (destination / "metrics.json.tmp").write_text(encoded, encoding="utf-8")
        (destination / "metrics.json.tmp").replace(destination / "metrics.json")
        return metadata
    finally:
        db.close()
