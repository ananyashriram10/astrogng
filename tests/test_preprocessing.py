import unittest

import numpy as np

from exoplanet_lab.preprocessing import preprocess_light_curve


class PreprocessingTests(unittest.TestCase):
    def test_cleans_sorts_and_normalizes(self):
        time = np.arange(60, dtype=float)[::-1]
        flux = 1.0 + 0.002 * np.sin(time / 8)
        flux[4] = np.nan
        clean_time, clean_flux = preprocess_light_curve(time, flux, window_length=11)
        self.assertTrue(np.all(np.diff(clean_time) > 0))
        self.assertAlmostEqual(float(np.median(clean_flux)), 1.0, places=7)
        self.assertTrue(np.isfinite(clean_flux).all())

    def test_rejects_mismatched_arrays(self):
        with self.assertRaises(ValueError):
            preprocess_light_curve([1] * 20, [1] * 21)


if __name__ == "__main__":
    unittest.main()

