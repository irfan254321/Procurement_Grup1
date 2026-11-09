"""Train CatBoost on actual BPI 2019 next activities, without synthetic policy labels."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from procurement.bpi import DEFAULT_DB, MODEL_DIR
from procurement.bpi_training import train


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--out", type=Path, default=MODEL_DIR)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--iterations", type=int, default=120)
    parser.add_argument("--train-documents", type=int, default=1500)
    parser.add_argument("--validation-documents", type=int, default=1000)
    parser.add_argument("--test-documents", type=int, default=1000)
    parser.add_argument("--max-prefixes-per-case", type=int, default=30)
    parser.add_argument("--threads", type=int, default=4)
    args = parser.parse_args()
    result = train(args.db, args.out, args.seed, args.iterations, args.train_documents,
                   args.validation_documents, args.test_documents, args.max_prefixes_per_case, args.threads)
    print(json.dumps({"run_id": result["run_id"], "samples": result["samples"],
                      "metrics": {k: v for k, v in result["metrics"].items()
                                  if k not in ("classification_report", "confusion_matrix", "confusion_labels")}}, indent=2))


if __name__ == "__main__":
    main()
