import unittest

from exoplanet_lab.catalog import normalize_koi_name, parse_kic_id, resolve_target_identifier


class IdentifierTests(unittest.TestCase):
    def test_koi_and_kic_forms_are_distinct_but_joinable(self):
        self.assertEqual(normalize_koi_name("KOI-752.01"), "K00752.01")
        self.assertEqual(parse_kic_id("KIC 10797460"), 10797460)
        resolved = resolve_target_identifier("K00752.01", allow_network=False)
        self.assertEqual(resolved.kepid, 10797460)
        self.assertEqual(resolved.mast_target, "KIC 10797460")
        self.assertEqual(resolved.kepoi_name, "K00752.01")


@unittest.skipUnless(
    __import__("importlib.util").util.find_spec("joblib")
    and __import__("importlib.util").util.find_spec("pandas"),
    "notebook dependencies are not installed",
)
class TrainedScorerTests(unittest.TestCase):
    def test_saved_model_accepts_runtime_feature_contract(self):
        from exoplanet_lab.scoring import TrainedKOIScorer

        scorer = TrainedKOIScorer()
        score = scorer.predict(
            {
                "period_days": 9.48,
                "duration_hours": 3.0,
                "depth_ppm": 900.0,
                "snr": 12.0,
                "num_transits_observed": 8,
                "stellar_radius_solar": 0.9,
            }
        )
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)


if __name__ == "__main__":
    unittest.main()

