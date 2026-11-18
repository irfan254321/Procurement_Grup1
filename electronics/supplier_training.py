"""Train supplier lateness/lead-time models from ONE Kaggle SCMS dataset.

No target or postdelivery column enters FEATURES. Repeated purchase orders stay
in one chronological partition; outcomes beyond the next partition are purged.
"""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime
from hashlib import sha256
import json
import math
from pathlib import Path
from statistics import median

import joblib
import numpy as np
from catboost import CatBoostClassifier, CatBoostRegressor
from sklearn.metrics import (
    accuracy_score, balanced_accuracy_score, brier_score_loss, f1_score,
    mean_absolute_error, precision_score, recall_score, roc_auc_score,
)

from supplier_data import (
    CATEGORICAL, DATASET_URL, FEATURES, MODEL_VERSION, SOURCE, SUPPLIER_DATA,
    load_supplier_models,
)


def parse_date(value):
    for form in ("%m/%d/%y", "%d-%b-%y", "%m/%d/%Y"):
        try:
            return datetime.strptime(value, form).date()
        except (ValueError, TypeError):
            continue
    return None


def number(value):
    try:
        result = float(value.replace(",", ""))
    except (ValueError, AttributeError):
        return None
    return result if math.isfinite(result) else None


def read_examples(path=SOURCE):
    result, excluded = [], Counter()
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    for raw in rows:
        ordered = parse_date(raw["PO Sent to Vendor Date"])
        scheduled = parse_date(raw["Scheduled Delivery Date"])
        delivered = parse_date(raw["Delivered to Client Date"])
        if ordered is None or scheduled is None or delivered is None:
            excluded["missing_order_or_outcome_date"] += 1
            continue
        scheduled_days, actual_days = (scheduled - ordered).days, (delivered - ordered).days
        if not (0 <= scheduled_days <= 730 and 0 <= actual_days <= 730):
            excluded["inconsistent_or_over_730_day_interval"] += 1
            continue
        quantity, price = number(raw["Line Item Quantity"]), number(raw["Pack Price"])
        if quantity is None or price is None or quantity <= 0 or price < 0:
            excluded["invalid_order_quantity_or_pack_price"] += 1
            continue
        cats = [raw[name].strip() or "Unknown" for name in (
            "Vendor", "Country", "Shipment Mode", "Fulfill Via", "Vendor INCO Term",
            "Product Group", "Sub Classification",
        )]
        features = cats + [math.log1p(quantity), math.log1p(price), scheduled_days,
                           ordered.month, ordered.year]
        result.append({
            "id": raw["ID"], "group": raw["PO / SO #"], "ordered": ordered,
            "delivered": delivered, "x": features, "lead": actual_days,
            "late": int(delivered > scheduled), "quantity": quantity, "price": price,
        })
    return result, {"source_rows": len(rows), "eligible_rows": len(result), "excluded": dict(excluded)}


def chronological_parts(examples):
    groups = defaultdict(list)
    for row in examples:
        groups[row["group"]].append(row)
    ordered_groups = sorted(groups, key=lambda group: (min(r["ordered"] for r in groups[group]), group))
    # Date boundaries keep same-day orders together, avoiding a misleading time split.
    desired_validation = min(r["ordered"] for r in groups[ordered_groups[int(len(groups) * .70)]])
    desired_test = min(r["ordered"] for r in groups[ordered_groups[int(len(groups) * .85)]])
    parts = [[], [], []]
    purged = [0, 0, 0]
    for group in ordered_groups:
        members = groups[group]
        first, last = min(r["ordered"] for r in members), max(r["ordered"] for r in members)
        index = 0 if first < desired_validation else 1 if first < desired_test else 2
        boundary = desired_validation if index == 0 else desired_test if index == 1 else None
        # Purge the whole PO if any row crosses the boundary or its outcome was not
        # yet known when the following partition began.
        if boundary and (last >= boundary or max(r["delivered"] for r in members) >= boundary):
            purged[index] += len(members)
            continue
        parts[index].extend(members)
    for part in parts:
        part.sort(key=lambda row: (row["ordered"], row["group"], row["id"]))
    if any(not part or len({r["late"] for r in part}) < 2 for part in parts):
        raise ValueError("Partisi kronologis tidak memuat cukup contoh kedua kelas.")
    return parts, {
        "method": "PO-grouped chronological 70/15/15 boundaries; purge outcomes unavailable at next split",
        "validation_start": desired_validation.isoformat(), "test_start": desired_test.isoformat(),
        "purged_rows": purged,
        "partitions": [
            {"name": name, "rows": len(part), "purchase_orders": len({r["group"] for r in part}),
             "start": min(r["ordered"] for r in part).isoformat(),
             "end": max(r["ordered"] for r in part).isoformat(),
             "late_count": sum(r["late"] for r in part)}
            for name, part in zip(("train", "validation", "test"), parts)
        ],
    }


def classification_metrics(y, probability, threshold):
    pred = np.asarray(probability) >= threshold
    return {
        "accuracy": float(accuracy_score(y, pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
        "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)),
        "f1": float(f1_score(y, pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y, probability)),
        "brier": float(brier_score_loss(y, probability)),
    }


def profiles_from_train(train):
    grouped = defaultdict(list)
    for row in train:
        grouped[row["x"][0]].append(row)
    leaders = sorted(grouped, key=lambda name: (-len(grouped[name]), name))[:5]
    result = []
    for index, vendor in enumerate(leaders):
        samples = grouped[vendor]
        common = lambda column: Counter(r["x"][column] for r in samples).most_common(1)[0][0]
        result.append({
            "profile_id": f"historical-{index+1}", "source_vendor": vendor,
            "country": common(1), "shipment_mode": common(2), "fulfill_via": common(3),
            "incoterm": common(4), "product_group": common(5), "sub_classification": common(6),
            "reference_quantity": float(median(r["quantity"] for r in samples)),
            "typical_unit_price": float(median(r["price"] for r in samples)),
            "scheduled_days": max(1, float(median(r["x"][9] for r in samples))),
            "order_month": common(10), "order_year": common(11),
            "historical_late_rate": round(sum(r["late"] for r in samples) / len(samples), 6),
            "source_rows": len(samples), "domain_transfer": True,
            "scope": "Health-commodity source profile transferred to local electronics simulation",
        })
    return result


def train():
    examples, cleaning = read_examples()
    parts, split = chronological_parts(examples)
    train_rows, validation_rows, test_rows = parts
    xs = [[r["x"] for r in part] for part in parts]
    late_labels = [[r["late"] for r in part] for part in parts]
    lead_labels = [[r["lead"] for r in part] for part in parts]
    shared = dict(iterations=260, depth=5, learning_rate=.055, random_seed=42,
                  thread_count=2, verbose=False, allow_writing_files=False, cat_features=list(CATEGORICAL))
    late = CatBoostClassifier(**shared, loss_function="Logloss", l2_leaf_reg=8)
    lead = CatBoostRegressor(**shared, loss_function="MAE", l2_leaf_reg=8)
    late.fit(xs[0], late_labels[0])
    # The known schedule is extremely strong in this source. Learn only the
    # deviation; retain the schedule baseline if validation does not improve.
    lead.fit(xs[0], [r["lead"] - r["x"][9] for r in train_rows])
    validation_prob = late.predict_proba(xs[1])[:, 1]
    thresholds = sorted(set([.5, *np.arange(.02, .301, .01).tolist()]))
    threshold = max(thresholds, key=lambda t: (
        balanced_accuracy_score(late_labels[1], validation_prob >= t),
        f1_score(late_labels[1], validation_prob >= t, zero_division=0), -abs(t - .5),
    ))
    validation_lead_pred = np.asarray([x[9] for x in xs[1]]) + lead.predict(xs[1])
    validation_reg_mae = mean_absolute_error(lead_labels[1], validation_lead_pred)
    validation_schedule_mae = mean_absolute_error(lead_labels[1], [x[9] for x in xs[1]])
    use_lead_model = validation_reg_mae < validation_schedule_mae - 1e-6
    late_report, lead_report = {}, {}
    training_prior = sum(late_labels[0]) / len(late_labels[0])
    for name, index in (("validation", 1), ("test", 2)):
        probability = late.predict_proba(xs[index])[:, 1]
        schedule = np.asarray([x[9] for x in xs[index]])
        lead_pred = np.clip(schedule + lead.predict(xs[index]), 0, 730)
        chosen_lead = lead_pred if use_lead_model else schedule
        late_report[name] = classification_metrics(late_labels[index], probability, threshold)
        late_report[name]["baseline_always_on_time_accuracy"] = 1 - sum(late_labels[index]) / len(late_labels[index])
        late_report[name]["baseline_balanced_accuracy"] = .5
        late_report[name]["baseline_prior_brier"] = float(brier_score_loss(late_labels[index], [training_prior] * len(xs[index])))
        lead_report[name] = {
            "mae_days": float(mean_absolute_error(lead_labels[index], chosen_lead)),
            "residual_model_mae_days": float(mean_absolute_error(lead_labels[index], lead_pred)),
            "baseline_scheduled_mae_days": float(mean_absolute_error(lead_labels[index], [x[9] for x in xs[index]])),
            "baseline_train_median_mae_days": float(mean_absolute_error(lead_labels[index], [median(lead_labels[0])] * len(xs[index]))),
        }
    report = {
        "model_version": MODEL_VERSION,
        "dataset": {"title": "Supply Chain Shipment Pricing Data", "kaggle_url": DATASET_URL,
                    "publisher": "USAID / Partnership for Supply Chain Management",
                    "domain": "Health commodity shipments, 2006-2015", "columns": 33,
                    "sha256": sha256(SOURCE.read_bytes()).hexdigest(),
                    "license_note": "Kaggle mirror lists Unknown; original catalog lists CC BY-ND 4.0 and publisher attribution. Original CSV retained unchanged.",
                    "catalog_url": "https://data.amerigeoss.org/dataset/supply-chain-shipment-pricing-data"},
        "cleaning": cleaning, "split": split,
        "features": list(FEATURES), "categorical_features": list(CATEGORICAL),
        "excluded_input_columns": ["Delivered to Client Date", "Delivery Recorded Date", "ASN/DN #", "Freight Cost (USD)", "Weight (Kilograms)"],
        "labels": {"late": "Delivered to Client Date > Scheduled Delivery Date",
                   "lead": "Days from PO Sent to Vendor Date to Delivered to Client Date"},
        "late": {"model": "CatBoostClassifier", "threshold": float(threshold), "threshold_selection": "maximum validation balanced accuracy",
                 "probability_calibrated": False, "class_weights": None,
                 "runtime_label": "Historical-domain model risk score, not calibrated electronics probability", **late_report},
        "lead": {"model": "CatBoostRegressor", "target": "Actual minus scheduled lead days",
                 "selected_model": "CatBoostResidual" if use_lead_model else "ScheduledBaseline",
                 "selection": "Use residual model only when validation MAE beats the known-schedule baseline", **lead_report},
        "limitations": [
            "Profiles and outcomes describe health commodity suppliers, not electronics vendors.",
            "Local vendor identity mapping, quantities, capacities, routes, and scaled days are simulation assumptions.",
            "No demand forecasting, stock/capacity prediction, damage prediction, or routing optimality is learned by these models.",
            "Scheduled delivery is a known requested commitment and is a strong feature; outcomes and actual shipment dates are labels only.",
            "Late events are rare; consult balanced accuracy, recall, ROC-AUC, Brier score and the majority baseline together.",
            "Publisher warns against literal item/country lead-time or cost conclusions; forecasts support a clearly labelled cross-domain demonstration.",
        ],
    }
    profiles = profiles_from_train(train_rows)
    SUPPLIER_DATA.mkdir(parents=True, exist_ok=True)
    artifact = {"model_version": MODEL_VERSION, "features": list(FEATURES), "late": late, "lead": lead}
    joblib.dump(artifact, SUPPLIER_DATA / "models.joblib", compress=3)
    (SUPPLIER_DATA / "metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (SUPPLIER_DATA / "profiles.json").write_text(json.dumps(profiles, indent=2), encoding="utf-8")
    with (SUPPLIER_DATA / "split_manifest.csv").open("w", encoding="utf-8", newline="") as target:
        writer = csv.writer(target)
        writer.writerow(["source_id", "purchase_order", "order_date", "outcome_date", "split"])
        for name, part in zip(("train", "validation", "test"), parts):
            writer.writerows((r["id"], r["group"], r["ordered"].isoformat(), r["delivered"].isoformat(), name) for r in part)
    load_supplier_models.cache_clear()
    print(json.dumps({"cleaning": cleaning, "split": split, "late": report["late"], "lead": report["lead"]}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ensure", action="store_true", help="Train only if models are absent or source/version changed")
    args = parser.parse_args()
    bundle = load_supplier_models()
    current_hash = sha256(SOURCE.read_bytes()).hexdigest() if SOURCE.is_file() else None
    if not SOURCE.is_file():
        raise SystemExit("Dataset SCMS belum tersedia. Lihat electronics/data/supplier/README.md.")
    if not args.ensure or bundle is None or bundle["report"]["dataset"]["sha256"] != current_hash:
        train()
    else:
        print("Model pemasok sudah sesuai sumber dan versi.")
