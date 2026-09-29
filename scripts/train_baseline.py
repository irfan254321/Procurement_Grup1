# PANDUAN MAHASISWA: Membuat data kandidat simulasi, memberi label pembanding, melatih empat classifier, dan menyimpan metrik/artefak.
"""Latih LR, SVM, Random Forest, dan XGBoost sebagai baseline laporan.

Contoh:
    python scripts/train_baseline.py --scenarios 600 --seed 42

Tanpa dataset historis eksternal, skrip membentuk keputusan kandidat dari
simulator dan memberi label memakai oracle kelayakan + biaya terbaik per
skenario. Sumber ini selalu dicatat sebagai data simulasi, bukan data riil.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score,
                             precision_score, recall_score, roc_auc_score)
from sklearn.model_selection import GroupShuffleSplit
from sklearn.calibration import CalibratedClassifierCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from xgboost import XGBClassifier

from procurement.baseline_ml import FEATURE_COLUMNS, decision_features
from procurement_marl.env import ProcurementEnv
from procurement_marl.evaluate import run_episode
from procurement_marl.oracle import PlanPolicy, all_plans
from procurement_marl.scenario import sample_scenario


def build_dataset(scenarios: int, seed: int) -> pd.DataFrame:
    """Bangun kandidat keputusan dan label optimal per skenario.

    Keputusan positif wajib layak dan biayanya maksimal 3% di atas biaya
    terendah yang layak. Sampel negatif dibatasi agar kelas tetap informatif.
    """
    rng = np.random.default_rng(seed)
    rows = []
    # Ruang penuh berisi 360 kombinasi. Ambil sampel tetap per skenario agar
    # penawaran balik dan revisi termin masuk dataset tanpa membuat latihan
    # terlalu berat. Seed menjamin kandidat yang sama dapat direproduksi.
    plan_space = all_plans(deterministic_only=False)
    for scenario_id in range(scenarios):
        scenario_seed = seed * 100_000 + scenario_id
        scenario = sample_scenario(scenario_seed)
        candidates = []
        plan_indices = rng.choice(len(plan_space), size=min(72, len(plan_space)), replace=False)
        plans = [plan_space[int(index)] for index in plan_indices]
        for plan_id, plan in enumerate(plans):
            result = run_episode(ProcurementEnv(scenario), PlanPolicy(plan), seed=scenario_seed,
                                 options={"scenario": scenario}, stop_at_first_check=True)
            features = decision_features(scenario, result)
            if features is not None:
                candidates.append((plan_id, result, features))
        feasible_costs = [result["total"] for _, result, _ in candidates if result["consensus"]]
        if not feasible_costs:
            # Tidak ada keputusan optimal yang dapat dipelajari untuk skenario ini.
            continue
        best_cost = min(feasible_costs)
        positive, negative = [], []
        for plan_id, result, features in candidates:
            optimal = bool(result["consensus"] and result["total"] <= best_cost * 1.03)
            row = {"scenario_id": scenario_id, "plan_id": plan_id, "label": int(optimal), **features}
            (positive if optimal else negative).append(row)
        # Banyak plan mentah dapat jatuh ke keputusan material yang sama karena
        # action mask. Batasi tiga positif dan ambil tiga negatif per positif
        # agar satu skenario tidak mendominasi dataset.
        keep_positive = min(len(positive), 3)
        positive_indices = rng.choice(len(positive), size=keep_positive, replace=False)
        selected_positive = [positive[int(i)] for i in positive_indices]
        keep_negative = min(len(negative), 3 * keep_positive)
        negative_indices = rng.choice(len(negative), size=keep_negative, replace=False) if keep_negative else []
        rows.extend(selected_positive)
        rows.extend(negative[int(i)] for i in negative_indices)
    frame = pd.DataFrame(rows)
    if frame.empty or frame["label"].nunique() != 2:
        raise RuntimeError("Dataset tidak memiliki dua kelas; tambah jumlah skenario.")
    return frame


def model_set(seed: int) -> dict:
    """Empat algoritma yang disebut dalam bagian Algorithm and AI Integration."""
    return {
        "Logistic Regression": make_pipeline(
            StandardScaler(), LogisticRegression(max_iter=2_000, class_weight="balanced", random_state=seed)
        ),
        "SVM": make_pipeline(
            StandardScaler(), CalibratedClassifierCV(
                SVC(kernel="rbf", class_weight="balanced", random_state=seed),
                method="sigmoid", cv=3,
            )
        ),
        "Random Forest": RandomForestClassifier(
            n_estimators=300, max_depth=12, min_samples_leaf=2,
            class_weight="balanced", n_jobs=1, random_state=seed,
        ),
        "XGBoost": XGBClassifier(
            n_estimators=300, max_depth=5, learning_rate=0.05,
            subsample=0.85, colsample_bytree=0.85, eval_metric="logloss",
            n_jobs=1, random_state=seed,
        ),
    }


def train(scenarios: int, seed: int, output: Path) -> dict:
    """Pisahkan berdasarkan skenario agar kandidat serupa tidak bocor ke test set."""
    data = build_dataset(scenarios, seed)
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.20, random_state=seed)
    train_index, test_index = next(splitter.split(data, data["label"], groups=data["scenario_id"]))
    train_data, test_data = data.iloc[train_index], data.iloc[test_index]
    x_train, y_train = train_data[FEATURE_COLUMNS], train_data["label"]
    x_test, y_test = test_data[FEATURE_COLUMNS], test_data["label"]

    models, metrics = model_set(seed), {}
    for name, model in models.items():
        model.fit(x_train, y_train)
        prediction = model.predict(x_test)
        probability = model.predict_proba(x_test)[:, 1]
        metrics[name] = {
            "accuracy": float(accuracy_score(y_test, prediction)),
            "precision": float(precision_score(y_test, prediction, zero_division=0)),
            "recall": float(recall_score(y_test, prediction, zero_division=0)),
            "f1": float(f1_score(y_test, prediction, zero_division=0)),
            "roc_auc": float(roc_auc_score(y_test, probability)),
            "confusion_matrix": confusion_matrix(y_test, prediction, labels=[0, 1]).tolist(),
        }

    output.mkdir(parents=True, exist_ok=True)
    comparator = "XGBoost"
    bundle = {"models": models, "features": FEATURE_COLUMNS, "comparator": comparator,
              "training_seed": seed, "dataset_version": 1}
    joblib.dump(bundle, output / "models.joblib", compress=3)
    report = {
        "comparator": comparator,
        "models": metrics,
        "dataset": {
            "source": "Keputusan kandidat dari simulator; label oracle kelayakan dan biaya (bukan data historis riil)",
            "scenarios_requested": scenarios,
            "scenarios_used": int(data["scenario_id"].nunique()),
            "rows": len(data),
            "train_rows": len(train_data),
            "test_rows": len(test_data),
            "positive_share": float(data["label"].mean()),
            "split": "80/20 berdasarkan scenario_id (GroupShuffleSplit)",
            "label_rule": "Optimal = layak dan biaya <= 103% biaya layak terendah dari kandidat pada skenario yang sama",
            "seed": seed,
        },
        "feature_columns": FEATURE_COLUMNS,
        "versions": {
            "python": sys.version.split()[0],
            "scikit_learn": __import__("sklearn").__version__,
            "xgboost": __import__("xgboost").__version__,
        },
    }
    (output / "metrics.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    data.to_csv(output / "dataset_simulasi.csv", index=False)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenarios", type=int, default=600)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "baseline")
    args = parser.parse_args()
    report = train(args.scenarios, args.seed, args.out)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
