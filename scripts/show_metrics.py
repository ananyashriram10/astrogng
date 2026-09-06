"""Print the saved classifier evaluation metrics in presentation-friendly form."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
METADATA = ROOT / "models" / "koi_candidate_classifier.metadata.json"


def main() -> int:
    if not METADATA.exists():
        print("No metrics file found. Train the model first with scripts/train_koi_classifier.py.")
        return 1
    metadata = json.loads(METADATA.read_text(encoding="utf-8"))
    metrics = metadata["test_metrics"]
    print(f"Model: {metadata['model_name']}")
    print(f"Dataset: {metadata['source_table']}")
    print(f"Train / validation / test: {metadata['training_rows']} / {metadata['validation_rows']} / {metadata['test_rows']}")
    print(f"ROC-AUC: {metrics['roc_auc']:.3f}")
    print(f"Average precision: {metrics['average_precision']:.3f}")
    print(f"Brier score: {metrics['brier_score']:.3f} (lower is better)")
    print(f"Decision threshold: {metadata['decision_threshold']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
