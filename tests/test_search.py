import unittest

import numpy as np

from exoplanet_lab.search import box_least_squares_search


class SearchTests(unittest.TestCase):
    def test_recovers_repeating_box_signal(self):
        rng = np.random.default_rng(42)
        time = np.arange(0, 45, 0.04)
        period = 3.2
        epoch = 0.7
        phase = ((time - epoch + period / 2) % period) - period / 2
        flux = 1.0 + rng.normal(0, 0.00018, time.size)
        flux[np.abs(phase) < 0.075] -= 0.005
        peak = box_least_squares_search(
            time, flux, min_period=2.7, max_period=3.7, period_steps=450
        )
        self.assertLess(abs(peak.period - period), 0.03)
        # Astropy returns the BLS objective in flux units; the NumPy fallback
        # returns an SNR-like statistic. Both are positive for a recovered dip.
        self.assertGreater(peak.power, 0)


if __name__ == "__main__":
    unittest.main()
