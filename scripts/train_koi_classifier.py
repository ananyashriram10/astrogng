"""Execute the complete NASA KOI training notebook from the repository root."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks" / "train_koi_classifier.ipynb"
OUTPUT = ROOT / "notebooks" / "train_koi_classifier.executed.ipynb"


def main() -> int:
    command = [
        sys.executable,
        "-m",
        "jupyter",
        "nbconvert",
        "--to",
        "notebook",
        "--execute",
        str(NOTEBOOK),
        "--output",
        str(OUTPUT),
        "--ExecutePreprocessor.timeout=1800",
    ]
    print("Downloading the NASA KOI table and training the classifier…", flush=True)
    subprocess.run(command, cwd=ROOT, check=True)
    print(f"Training complete. Model written to {ROOT / 'models' / 'koi_candidate_classifier.joblib'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
