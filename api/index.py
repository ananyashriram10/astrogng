"""Vercel entrypoint for the Exoplanet Transit Lab FastAPI service."""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from exoplanet_lab.api import app  # noqa: E402

