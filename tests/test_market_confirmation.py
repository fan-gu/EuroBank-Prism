"""Tests for the independent price-confirmation axis."""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from build_market_confirmation import return_since, score_records


class MarketConfirmationTests(unittest.TestCase):
    def test_return_since_uses_requested_number_of_sessions(self):
        self.assertAlmostEqual(return_since([100.0, 105.0, 110.0], 2), 0.10)
        self.assertIsNone(return_since([100.0, 110.0], 2))

    def test_peer_score_is_independent_and_has_a_regime(self):
        records = [
            {"ticker": "A", "one_month_return": 0.10, "three_month_return": 0.12, "six_month_return": 0.20, "trend_vs_200d": 0.10},
            {"ticker": "B", "one_month_return": 0.00, "three_month_return": 0.02, "six_month_return": 0.03, "trend_vs_200d": 0.01},
            {"ticker": "C", "one_month_return": -0.10, "three_month_return": -0.08, "six_month_return": -0.05, "trend_vs_200d": -0.10},
        ]
        scored = score_records(records)
        self.assertGreater(scored[0]["price_confirmation_score"], scored[2]["price_confirmation_score"])
        self.assertEqual(scored[0]["price_regime"], "Confirming")
        self.assertEqual(scored[2]["price_regime"], "Unconfirmed")
        self.assertNotIn("numeric_score", scored[0])


if __name__ == "__main__":
    unittest.main()
