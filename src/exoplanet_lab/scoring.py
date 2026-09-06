from __future__ import annotations

import math
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_PATH = PROJECT_ROOT / "models" / "koi_candidate_classifier.joblib"
DEFAULT_ASTROGNG_DIR = PROJECT_ROOT / "models" / "astrogng"


class CandidateScorer(Protocol):
    model_name: str
    threshold: float

    def predict(self, features: Mapping[str, float | int | list[float]]) -> float: ...


class HeuristicCandidateScorer:
    """Transparent baseline scorer, replaceable by a trained model later."""

    model_name = "heuristic-v1"
    threshold = 0.5

    def predict(self, features: Mapping[str, float | int | list[float]]) -> float:
        snr = float(features["snr"])
        depth = float(features["depth_ppm"])
        events = int(features["num_transits_observed"])
        odd_even = float(features["odd_even_depth_diff_ppm"])
        secondary = float(features["secondary_eclipse_depth_ppm"])
        symmetry = float(features["transit_shape_symmetry"])

        logit = -2.2
        logit += min(snr, 20.0) * 0.19
        logit += min(events, 6) * 0.20
        logit += (symmetry - 0.5) * 1.6
        if depth > 30_000:
            logit -= 1.4
        elif depth > 15_000:
            logit -= 0.6
        logit -= min(odd_even / max(depth, 50.0), 2.0) * 1.7
        logit -= min(secondary / max(depth, 50.0), 2.0) * 2.2
        return float(np_clip(1.0 / (1.0 + math.exp(-logit)), 0.01, 0.99))


class TrainedKOIScorer:
    """Adapter for the calibrated model bundle exported by the training notebook."""

    def __init__(self, model_path: Path | str = DEFAULT_MODEL_PATH) -> None:
        try:
            import joblib
            import numpy as np
            import pandas as pd
        except ImportError as exc:
            raise RuntimeError(
                "The trained scorer requires pandas, joblib, and scikit-learn. "
                "Install notebooks/requirements.txt."
            ) from exc

        self._np = np
        self._pd = pd
        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Trained model not found at {self.model_path}. Run the training notebook first."
            )
        # joblib uses pickle internally; load only the locally trained project artifact.
        bundle = joblib.load(self.model_path)
        required = {"model", "model_name", "feature_columns", "decision_threshold"}
        missing = required - set(bundle)
        if missing:
            raise ValueError(f"Model bundle is missing required keys: {sorted(missing)}")
        self._model = bundle["model"]
        self.model_name = str(bundle["model_name"])
        self.feature_columns = list(bundle["feature_columns"])
        self.threshold = float(bundle["decision_threshold"])

    def predict(self, features: Mapping[str, float | int | list[float]]) -> float:
        row: dict[str, float] = {}
        for column in self.feature_columns:
            value = features.get(column, self._np.nan)
            row[column] = float(value) if not isinstance(value, list) and value is not None else self._np.nan
        frame = self._pd.DataFrame([row], columns=self.feature_columns)
        return float(self._model.predict_proba(frame)[0, 1])


class AstroGNGEnsembleScorer:
    """The astrogng ensemble: XGBoost over BLS/KOI-style scalar features, an
    AstroNet-style dual-input CNN over phase-folded global/local views, and a
    logistic-regression meta-model that blends both probabilities into the
    final confidence.
    """

    model_name = "astrogng-ensemble-v1"
    threshold = 0.5

    def __init__(self, bundle_dir: Path | str = DEFAULT_ASTROGNG_DIR) -> None:
        bundle_dir = Path(bundle_dir)
        gbt_path = bundle_dir / "gbt_model_v2.json"
        cnn_path = bundle_dir / "cnn_transit_model_final.keras"
        meta_path = bundle_dir / "meta_model.joblib"
        missing = [p.name for p in (gbt_path, cnn_path, meta_path) if not p.exists()]
        if missing:
            raise FileNotFoundError(
                f"astrogng model bundle is missing {missing} under {bundle_dir}"
            )

        try:
            import joblib
            import numpy as np
            import pandas as pd
            import xgboost as xgb
        except ImportError as exc:
            raise RuntimeError(
                "The astrogng ensemble scorer requires xgboost, pandas, joblib, "
                "and scikit-learn. Install notebooks/requirements.txt."
            ) from exc
        try:
            import tensorflow as tf
        except ImportError as exc:
            raise RuntimeError(
                "The astrogng ensemble scorer requires tensorflow to load its CNN. "
                "Install it with `pip install tensorflow`."
            ) from exc

        self._np = np
        self._pd = pd
        self._xgb = xgb
        self._gbt = xgb.Booster()
        self._gbt.load_model(str(gbt_path))
        self._gbt_features = [
            "koi_period",
            "koi_duration",
            "koi_depth",
            "koi_model_snr",
            "koi_num_transits",
        ]
        self._cnn = tf.keras.models.load_model(str(cnn_path))
        self._meta = joblib.load(meta_path)

        self.last_gbt_proba: float | None = None
        self.last_cnn_proba: float | None = None

    def predict(self, features: Mapping[str, float | int | list[float]]) -> float:
        gbt_row = {
            "koi_period": features["period_days"],
            "koi_duration": features["duration_hours"],
            "koi_depth": features["depth_ppm"],
            "koi_model_snr": features["snr"],
            "koi_num_transits": features["num_transits_observed"],
        }
        gbt_frame = self._pd.DataFrame([gbt_row], columns=self._gbt_features)
        gbt_matrix = self._xgb.DMatrix(gbt_frame, feature_names=self._gbt_features)
        gbt_proba = float(self._gbt.predict(gbt_matrix)[0])

        global_view = features.get("global_view")
        local_view = features.get("local_view")
        if global_view and local_view:
            global_arr = self._np.asarray(global_view, dtype=float)[None, :, None]
            local_arr = self._np.asarray(local_view, dtype=float)[None, :, None]
            cnn_proba = float(self._cnn.predict([global_arr, local_arr], verbose=0)[0, 0])
        else:
            cnn_proba = 0.5

        self.last_gbt_proba = round(gbt_proba, 4)
        self.last_cnn_proba = round(cnn_proba, 4)

        meta_row = self._pd.DataFrame(
            [[gbt_proba, cnn_proba]], columns=["gbt_proba", "cnn_proba"]
        )
        return float(self._meta.predict_proba(meta_row)[0, 1])


def load_candidate_scorer(
    model_path: Path | str = DEFAULT_MODEL_PATH,
    *,
    require_trained: bool = False,
) -> CandidateScorer:
    try:
        return AstroGNGEnsembleScorer()
    except (FileNotFoundError, RuntimeError):
        pass
    try:
        return TrainedKOIScorer(model_path)
    except (FileNotFoundError, RuntimeError):
        if require_trained:
            raise
        return HeuristicCandidateScorer()


def np_clip(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))
