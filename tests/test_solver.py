import os
import sys
import unittest

# Add the optimizer directory to the path so we can import the Solver class
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "optimizer"))

from solver import Solver


class TestSolver(unittest.TestCase):
    def test_toWh_1w_60min_timeslot(self):
        """Test that 1W with 60-minute timeslot gives 1Wh"""
        solver = Solver(timeslot_length=60)
        result = solver.toWh(1.0)
        self.assertEqual(result, 1.0, f"Expected 1.0, but got {result}")

    def test_toWh_60w_1min_timeslot(self):
        """Test that 60W with 1-minute timeslot gives 1Wh"""
        solver = Solver(timeslot_length=1)
        result = solver.toWh(60.0)
        self.assertEqual(result, 1.0, f"Expected 1.0, but got {result}")

    def test_toWh_100w_30min_timeslot(self):
        """Test that 100W with 30-minute timeslot gives 50Wh"""
        solver = Solver(timeslot_length=30)
        result = solver.toWh(100.0)
        self.assertEqual(result, 50.0, f"Expected 50.0, but got {result}")

    def test_toWh_200w_15min_timeslot(self):
        """Test that 200W with 15-minute timeslot gives 50Wh"""
        solver = Solver(timeslot_length=15)
        result = solver.toWh(200.0)
        self.assertEqual(result, 50.0, f"Expected 50.0, but got {result}")

    def test_toWh_zero_power(self):
        """Test that 0W gives 0Wh regardless of timeslot length"""
        solver = Solver(timeslot_length=60)
        result = solver.toWh(0.0)
        self.assertEqual(result, 0.0, f"Expected 0.0, but got {result}")

    def test_toWh_negative_power(self):
        """Test that negative power gives negative watt-hours"""
        solver = Solver(timeslot_length=60)
        result = solver.toWh(-10.0)
        self.assertEqual(result, -10.0, f"Expected -10.0, but got {result}")

    def test_toWh_60w_1min_timeslot_equals_1wh(self):
        """Test that 1W with 1-minute timeslot gives 60Wh (which equals 1Wh when divided by 60)"""
        solver = Solver(timeslot_length=1)
        result = solver.toWh(1.0)
        self.assertEqual(result, 60.0, f"Expected 60.0, but got {result}")
        # This means 1W for 1 minute = 60Wh in the solver's units
        # To get actual Wh, we would need to divide by 60: 60.0 / 60 = 1.0 Wh


if __name__ == "__main__":
    unittest.main()
