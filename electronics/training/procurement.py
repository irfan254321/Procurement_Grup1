"""Benchmark each role on scenario labels anchored to the procurement CSV."""
import json
import sys
from hashlib import sha256
from pathlib import Path
from random import Random

import joblib
from catboost import CatBoostClassifier
from scipy.optimize import linear_sum_assignment
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier
from xgboost import XGBClassifier

from domain import AGENTS, DATA, MODEL_VERSION, load_models, make_catalog, read_purchases, targets

SEED = 42


def candidates():
    return {
        "Decision Tree": DecisionTreeClassifier(max_depth=6, min_samples_leaf=12, random_state=SEED),
        "Random Forest": RandomForestClassifier(n_estimators=80, max_depth=9, min_samples_leaf=5, random_state=SEED),
        "Extra Trees": ExtraTreesClassifier(n_estimators=80, max_depth=10, min_samples_leaf=4, random_state=SEED),
        "Gradient Boosting": GradientBoostingClassifier(max_depth=3, random_state=SEED),
        "Logistic Regression": make_pipeline(StandardScaler(), LogisticRegression()),
        "SVM": make_pipeline(StandardScaler(), SVC()),
        "KNN": make_pipeline(StandardScaler(), KNeighborsClassifier(n_neighbors=19)),
        "CatBoost": CatBoostClassifier(iterations=120, depth=5, verbose=False, thread_count=2,
                                       allow_writing_files=False, random_seed=SEED),
        "XGBoost": XGBClassifier(n_estimators=100, max_depth=4, learning_rate=.1, n_jobs=2, random_state=SEED),
    }


def examples(rows, seed):
    rng = Random(seed)
    stock_rng = Random(seed + 10_000)
    catalog = make_catalog(rows)
    result = {role: ([], []) for role in AGENTS}
    for _ in range(1600):
        item = rng.choice(catalog)
        ref = item["reference"]
        price = rng.choice(item["vendors"])["price"]
        demand = rng.randint(1, 10)
        stock = rng.randint(0, 18)
        need = rng.randint(6, 18)
        order_cost = round(price * need, 2)
        vectors = {
            "stock": [stock_rng.randint(0, 30), stock_rng.randint(0, 18), rng.randint(2, 6)],
            "finance": [order_cost, round(order_cost*rng.uniform(.5, 2), 4),
                        round(order_cost*rng.uniform(.8, 1.7), 2)],
            "seller": [stock, demand, ref*rng.uniform(1.15, 1.75)],
            "buyer": [ref*rng.uniform(1.15, 1.75), ref*rng.uniform(1.05, 1.85), demand],
            "procurement": [price*rng.uniform(.95, 1.15), ref, rng.randint(4, 24), need],
            "vendor": [price*rng.uniform(.70, 1.18), price*.9, need, rng.randint(5, 28)],
            "deal": [price*rng.uniform(.72, 1.2), ref*rng.uniform(.85, 1.2), price*.88],
        }
        for role, vector in vectors.items():
            result[role][0].append(vector)
            result[role][1].append(int(targets(role, vector)))
    return result


def train():
    rows = sorted((r for r in read_purchases() if r["Category"] == "Electronics"),
                  key=lambda r: (r["PurchaseDate"], r["TransactionID"]))
    parts = (rows[:100], rows[100:123], rows[123:])
    train_set, validation, test = [examples(part, SEED+i) for i, part in enumerate(parts)]
    names = list(candidates())
    metrics, fitted = {}, {}
    for role in AGENTS:
        metrics[role], fitted[role] = {}, {}
        x, y = train_set[role]
        vx, vy = validation[role]
        for name, model in candidates().items():
            model.fit(x, y)
            pred = model.predict(vx)
            metrics[role][name] = {"validation": float(balanced_accuracy_score(vy, pred))}
            fitted[role][name] = model
    weights = [[metrics[role][name]["validation"] for name in names] for role in AGENTS]
    indices, choices = linear_sum_assignment(weights, maximize=True)
    output = {"model_version": MODEL_VERSION, "source_rows": [len(p) for p in parts], "scenarios_per_split": 1600,
              "source_sha256": sha256((DATA / "spend_analysis_dataset.csv").read_bytes()).hexdigest(),
              "agents": {}}
    active = {}
    for idx, choice in zip(indices, choices):
        role = list(AGENTS)[idx]
        main = names[choice]
        backups = sorted((name for name in names if name != main),
                         key=lambda n: (-metrics[role][n]["validation"], n))[:4]
        selected = [main, *backups]
        tx, ty = test[role]
        for name in names:
            pred = fitted[role][name].predict(tx)
            metrics[role][name].update(accuracy=float(accuracy_score(ty, pred)),
                                       balanced=float(balanced_accuracy_score(ty, pred)))
        output["agents"][role] = {"main": main, "selected": selected, "candidates": metrics[role],
                                   "baseline": max(sum(ty), len(ty)-sum(ty))/len(ty)}
        active[role] = {name: fitted[role][name] for name in selected}
        print(role, main, round(metrics[role][main]["accuracy"] * 100, 2), flush=True)
    joblib.dump({"model_version": MODEL_VERSION, "agents": active}, DATA / "models.joblib", compress=3)
    (DATA / "metrics.json").write_text(json.dumps(output, indent=2), encoding="utf-8")


def main():
    if "--ensure" not in sys.argv or load_models() is None:
        train()
