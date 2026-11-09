# CatBoost — BPI Challenge 2019

## What is learned

One CatBoost multiclass model predicts the **next recorded procurement activity**
given the events already observed for a purchase-order item. Every training label
is an actual next event in the dataset, such as `Change Price`,
`Record Goods Receipt`, `Record Invoice Receipt`, or `Clear Invoice`.

This is supervised learning of historical behavior. It does not prove that the
predicted action is optimal and does not execute purchases or payments.
No expert/simulator-generated action labels are mixed into BPI training.

## Source and provenance

- Creator: Boudewijn van Dongen (2019), *BPI Challenge 2019*, Version 1,
  4TU.ResearchData.
- DOI: https://doi.org/10.4121/uuid:d06aff4b-79f0-45e6-8ec8-e19730c248f1
- Official record: https://data.4tu.nl/datasets/35ed7122-966a-484e-a0e1-749b64e3366d
- License: **CC BY 4.0**. Preserve this attribution when sharing derived work.
- Official uncompressed XES MD5: `4eb909242351193a61e1c15b9c3cc814`.
- XES SHA-256: `af63bc687fc4152f2123b05c3af7772b37ef3fce2d3f67f812666c9e356baae7`.
- Full dataset: **251,734 cases / 1,595,923 events**, representing 76,349
  purchasing documents. One document can contain multiple cases/items.
- Monetary values and identities are anonymized. The EUR values must not be
  treated as real vendor prices or converted into the old rupiah fixture.

## Features and label availability

The input is a prefix of a single case: the latest three observed activities,
prefix length, time gaps, observed cumulative net worth and its observed change,
calendar fields of the latest observed event, and counts of nine named activities
within that prefix. The target is the next event's original activity name.

No document/case IDs, next timestamp, future event counts, final outcomes,
future invoice values, or labels enter the feature vector. Trace-level snapshots
(including vendor, category and flags) are stored for browsing but deliberately
excluded from features: the log does not establish that each snapshot attribute
was already known at the prefix date.

Pairs with equal timestamps are excluded because their causal order is ambiguous.
Within observed prefixes, the source XES order is retained. No `END` label is
invented from the last event: an incomplete observation window is not necessarily
a completed procurement process.

## Split and evaluation

The 70th and 85th percentiles of document start times define chronological cutoffs.
All items from a purchasing document belong to the same partition. A training
document must end before the first cutoff; a validation document must start after
the first and end before the second; a test document must start after the second.
Documents crossing these boundaries are excluded and counted in the metadata.
This can underrepresent long-running or complex cases; evaluation is not a claim
about every transaction in the original dataset.

The first training run uses reproducibly sampled documents from each partition,
with at most 30 valid prefixes per case. The complete imported data stays in SQLite.
The active `runs/bpi_catboost/metrics.json` records the actual sample counts,
cutoffs, seed, library versions, excluded ties, and hyperparameters.

Early stopping uses validation only. Unseen validation labels are excluded from
CatBoost's early-stopping set and their count is recorded. Unseen test labels are
**retained** as prediction failures. The final test set does not select models.

Metrics include accuracy, macro-F1, weighted-F1, top-3 accuracy, per-class
precision/recall/support, and a confusion matrix. Two baselines learned only from
training data are reported: majority next activity, and most frequent next
activity conditional on the current activity. A large accuracy can conceal poor
performance on rare activities; inspect macro-F1 and class-level results.

Only CatBoost has been trained in this upgrade. No claim of superiority over
Decision Tree or SVM is made.

### Initial measured run

Run `20261107T150752Z-517d9edd`, seed 42: 19,146 training prefixes, 7,248 validation
prefixes, and 12,698 test prefixes. CatBoost 1.2.10, 120 trees of depth 5.
The selected documents are 1,500 / 1,000 / 1,000 respectively; this is a sampled
experiment, not training on all 1.6 million events.

| Held-out metric | Result |
|---|---:|
| Accuracy | 71.87% |
| Macro-F1 | 0.2384 |
| Weighted-F1 | 0.6811 |
| Top-3 accuracy | 92.21% |
| Majority baseline accuracy | 24.35% |
| Last-activity baseline accuracy | 55.73% |

Thirty test labels were unseen in training and remained in the denominator.
Recall for `Change Price` and `Change Quantity` is **0** in this run; the model
must not be presented as a validated negotiation/quantity decision agent.
Clear Invoice recall is approximately 96.29%, whereas Remove Payment Block
recall is approximately 21.90%. The full class-level results are retained in
the metrics file and shown in the app. These results were inspected after the
model was fitted, and were not used to select an alternative checkpoint.

## Relation to the four original agents

| Original agent task | What BPI does and does not supply |
|---|---|
| IRE: split/defer an urgent request | Quantity changes are events, but labels for urgent allocation and funding decisions are absent. |
| VMI: choose from vendor offers A/B/C | Historical chosen vendors are recorded; candidate offers and rejected alternatives are absent. |
| DA: accept/counteroffer/alternative | `Change Price` is a recorded revision, not a labelled counteroffer or negotiation outcome. |
| SLM: fast/due/split payment | Invoice events are recorded; the simulator's three payment modes are not labelled. |

Consequently this model is **not** passed into the old MARL action interface, and
the app does not claim to have trained four CatBoost agent policies. The old
simulator remains in a separate mode. A compatible decision-labelled dataset is
needed before replacing those exact four policies.

## Database and reproducibility

`data/bpi2019.sqlite3` contains dataset provenance, cases, events, training runs,
document partitions and prediction audits. Training artifacts are stored in
`runs/bpi_catboost/<run_id>/`: native `.cbm` model, metadata and three manifests.
Active artifacts are also exposed at `runs/bpi_catboost/model.cbm` and `metrics.json`.
Manifest files contain actual evaluated prefix IDs so the experiment can be audited.

Raw data and SQLite are excluded from Git. After a clone, `prepare_bpi.py`
downloads and verifies the official dataset, then registers any shipped model
and its manifests. Repeated imports of the same checksum are idempotent.
Existing MARL history in `data/procurement.sqlite3` is untouched.

The UI predicts from a selected observed prefix, logs the prediction, and shows
the actual next event separately. That actual future event is never a feature.
