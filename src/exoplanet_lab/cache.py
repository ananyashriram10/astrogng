from __future__ import annotations

import json
import re
from pathlib import Path

from .demo_data import DEMO_TARGETS, build_demo_result, find_demo_target
from .models import AnalysisResult


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_DIR = PROJECT_ROOT / "cache"


def target_slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")
    if not slug:
        raise ValueError("target name must include a letter or number")
    return slug


class ResultCache:
    def __init__(self, directory: Path | str = DEFAULT_CACHE_DIR) -> None:
        self.directory = Path(directory)

    def path_for(self, target: str) -> Path:
        return self.directory / f"{target_slug(target)}.json"

    def save(self, result: AnalysisResult) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.path_for(result.target)
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(result.to_dict(), separators=(",", ":")), encoding="utf-8")
        temporary.replace(path)
        return path

    def load(self, target: str) -> AnalysisResult | None:
        path = self.path_for(target)
        if path.exists():
            return AnalysisResult.from_dict(json.loads(path.read_text(encoding="utf-8")))
        demo = find_demo_target(target)
        return build_demo_result(demo) if demo else None

    def list_targets(self) -> list[dict[str, str | int | bool]]:
        return [
            {
                "target": item.name,
                "mission": item.mission,
                "candidate_count": len(item.planets),
                "is_multi_planet": len(item.planets) > 1,
            }
            for item in DEMO_TARGETS
        ]

    def generate_all(self) -> list[Path]:
        return [self.save(build_demo_result(target)) for target in DEMO_TARGETS]

