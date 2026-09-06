"""Fetch a KOI/KIC light curve from MAST and print model predictions."""

from __future__ import annotations

import argparse
import json

from exoplanet_lab.service import ArchiveAnalysisOptions, analyze_archive_target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", help="KOI (e.g. K00752.01), KIC ID, or object name")
    parser.add_argument("--mission", choices=["Kepler", "TESS"], default="Kepler")
    parser.add_argument("--max-files", type=int, default=4)
    parser.add_argument("--blind", action="store_true", help="Do not use a NASA KOI period hint")
    args = parser.parse_args()
    result = analyze_archive_target(
        args.target,
        ArchiveAnalysisOptions(
            mission=args.mission,
            max_files=args.max_files,
            use_catalog_period_hint=not args.blind,
            require_trained_model=True,
        ),
    )
    print(json.dumps(result.to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
