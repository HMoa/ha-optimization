from __future__ import annotations

import os
import sys
import unittest

# Add the optimizer directory to the path so we can import the Solver class
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "optimizer"))

from optimizer.solver import Solver


class TestSolver(unittest.TestCase):
    def test_toWh_1w_60min_timeslot(self) -> None:
        """Test that 1W with 60-minute timeslot gives 1Wh"""
        solver = Solver(timeslot_length=60)
        result = solver.toWh(1.0)
        self.assertEqual(result, 1.0, f"Expected 1.0, but got {result}")

    def test_toWh_60w_1min_timeslot(self) -> None:
        """Test that 60W with 1-minute timeslot gives 1Wh"""
        solver = Solver(timeslot_length=1)
        result = solver.toWh(60.0)
        self.assertEqual(result, 1.0, f"Expected 1.0, but got {result}")

    def test_toWh_100w_30min_timeslot(self) -> None:
        """Test that 100W with 30-minute timeslot gives 50Wh"""
        solver = Solver(timeslot_length=30)
        result = solver.toWh(100.0)
        self.assertEqual(result, 50.0, f"Expected 50.0, but got {result}")

    def test_toWh_200w_15min_timeslot(self) -> None:
        """Test that 200W with 15-minute timeslot gives 50Wh"""
        solver = Solver(timeslot_length=15)
        result = solver.toWh(200.0)
        self.assertEqual(result, 50.0, f"Expected 50.0, but got {result}")

    def test_toWh_zero_power(self) -> None:
        """Test that 0W gives 0Wh regardless of timeslot length"""
        solver = Solver(timeslot_length=60)
        result = solver.toWh(0.0)
        self.assertEqual(result, 0.0, f"Expected 0.0, but got {result}")

    def test_toWh_negative_power(self) -> None:
        """Test that negative power gives negative watt-hours"""
        solver = Solver(timeslot_length=60)
        result = solver.toWh(-10.0)
        self.assertEqual(result, -10.0, f"Expected -10.0, but got {result}")


if __name__ == "__main__":
    unittest.main()
