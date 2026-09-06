from __future__ import annotations

from exoplanet_lab.cache import ResultCache


if __name__ == "__main__":
    paths = ResultCache().generate_all()
    for path in paths:
        print(path)

