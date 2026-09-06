import tempfile
import unittest
from pathlib import Path

from exoplanet_lab.cache import ResultCache, target_slug
from exoplanet_lab.demo_data import DEMO_TARGETS, build_demo_result


class CacheTests(unittest.TestCase):
    def test_slug_is_filesystem_safe(self):
        self.assertEqual(target_slug("TRAPPIST-1"), "trappist-1")
        self.assertEqual(target_slug("KOI / sample"), "koi-sample")

    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = ResultCache(Path(directory))
            expected = build_demo_result(DEMO_TARGETS[0])
            cache.save(expected)
            actual = cache.load(expected.target)
            self.assertIsNotNone(actual)
            self.assertEqual(actual.target, expected.target)
            self.assertEqual(len(actual.candidates), len(expected.candidates))


if __name__ == "__main__":
    unittest.main()

