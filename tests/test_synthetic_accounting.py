import unittest
from polymarket_arbitrage.data import OrderBookSnapshot
from polymarket_arbitrage.backtest import build_default_backtester


class SyntheticAccountingTest(unittest.TestCase):
    def test_eligible_pair_settlement(self):
        snapshot = OrderBookSnapshot(0, [(0.40, 10)], [(0.44, 10)], [(0.48, 10)], [(0.50, 10)])
        result = build_default_backtester([snapshot], 0.01, 0.02, 1, 900).run()
        self.assertAlmostEqual(result.total_pnl, 0.04)
        self.assertEqual(result.trades, 1)
        self.assertEqual(result.max_open_positions, 1)

    def test_ineligible_pair_is_skipped(self):
        snapshot = OrderBookSnapshot(0, [(0.47, 10)], [(0.51, 10)], [(0.48, 10)], [(0.51, 10)])
        result = build_default_backtester([snapshot], 0.01, 0.02, 1, 900).run()
        self.assertEqual(result.total_pnl, 0)
        self.assertEqual(result.trades, 0)
