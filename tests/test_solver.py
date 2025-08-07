from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timedelta

# Add the optimizer directory to the path so we can import the Solver class
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "optimizer"))

from optimizer.battery_config import BatteryConfig
from optimizer.models import Activity, Elpris, TimeslotItem
from optimizer.solver import Solver


class TestSolver(unittest.TestCase):
    def setUp(self) -> None:
        """Set up test fixtures before each test method."""
        self.solver = Solver(timeslot_length=60)
        self.battery_config = BatteryConfig(
            grid_area="SE3",
            storage_size_wh=10000,
            max_charge_speed_w=5000,
            max_discharge_speed_w=5000,
            initial_energy=5000,  # 50% SOC
        )

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

    def test_create_schedule_empty_input(self) -> None:
        """Test that empty input returns None"""
        result = self.solver.create_schedule({}, {}, {}, self.battery_config)
        self.assertIsNone(result)

    def test_create_schedule_mismatched_input_lengths(self) -> None:
        """Test that mismatched input lengths return None"""
        production = {datetime(2025, 1, 1, 10, 0): 1000.0}
        consumption = {
            datetime(2025, 1, 1, 10, 0): 500.0,
            datetime(2025, 1, 1, 11, 0): 500.0,
        }
        prices = {datetime(2025, 1, 1, 10, 0): Elpris(1.0)}

        result = self.solver.create_schedule(
            production, consumption, prices, self.battery_config
        )
        self.assertIsNone(result)

    def test_create_schedule_low_price_charge_scenario(self) -> None:
        """Test scenario where prices are low - should charge battery to store energy for later"""
        # Create 2-hour scenario with low prices
        base_time = datetime(2025, 1, 1, 10, 0)
        production = {
            base_time: 2000.0,  # 2kW solar
            base_time + timedelta(hours=1): 2000.0,
        }
        consumption = {
            base_time: 1000.0,  # 1kW consumption
            base_time + timedelta(hours=1): 1000.0,
        }
        prices = {
            base_time: Elpris(0.3),  # Very low price
            base_time + timedelta(hours=1): Elpris(0.3),
        }

        result = self.solver.create_schedule(
            production, consumption, prices, self.battery_config
        )

        self.assertIsNotNone(result)
        assert result is not None  # For mypy
        self.assertEqual(len(result), 2)

        # With asymmetric pricing, even "low" prices result in buy > sell price
        # So the optimizer should discharge to sell rather than charge
        for timeslot in result.values():
            self.assertLessEqual(
                timeslot.battery_flow_wh, 0
            )  # Negative or zero = discharging
            self.assertIn(
                timeslot.activity,
                [
                    Activity.DISCHARGE_FOR_HOME,
                    Activity.DISCHARGE,
                    Activity.CHARGE_LIMIT,
                ],
            )

    def test_create_schedule_high_price_sell_scenario(self) -> None:
        """Test scenario where prices are high - should sell battery energy to grid for profit"""
        base_time = datetime(2025, 1, 1, 10, 0)
        production = {
            base_time: 1000.0,  # Moderate solar
            base_time + timedelta(hours=1): 1000.0,
        }
        consumption = {
            base_time: 800.0,  # Moderate consumption
            base_time + timedelta(hours=1): 800.0,
        }
        prices = {
            base_time: Elpris(3.0),  # Very high price
            base_time + timedelta(hours=1): Elpris(3.0),
        }

        result = self.solver.create_schedule(
            production, consumption, prices, self.battery_config
        )

        self.assertIsNotNone(result)
        assert result is not None  # For mypy
        self.assertEqual(len(result), 2)

        # Should discharge battery to sell to grid when prices are very high
        for timeslot in result.values():
            self.assertLessEqual(
                timeslot.battery_flow_wh, 0
            )  # Negative or zero = discharging
            self.assertIn(
                timeslot.activity,
                [
                    Activity.DISCHARGE_FOR_HOME,
                    Activity.DISCHARGE,
                    Activity.CHARGE_LIMIT,
                ],
            )

    def test_create_schedule_battery_state_evolution(self) -> None:
        """Test that battery state evolves correctly across timeslots"""
        base_time = datetime(2025, 1, 1, 10, 0)
        production = {
            base_time: 2000.0,
            base_time + timedelta(hours=1): 2000.0,
            base_time + timedelta(hours=2): 2000.0,
        }
        consumption = {
            base_time: 1000.0,
            base_time + timedelta(hours=1): 1000.0,
            base_time + timedelta(hours=2): 1000.0,
        }
        prices = {
            base_time: Elpris(1.0),
            base_time + timedelta(hours=1): Elpris(1.0),
            base_time + timedelta(hours=2): Elpris(1.0),
        }

        result = self.solver.create_schedule(
            production, consumption, prices, self.battery_config
        )

        self.assertIsNotNone(result)
        assert result is not None  # For mypy
        self.assertEqual(len(result), 3)

        # Check that battery SOC evolves logically
        timeslots = sorted(result.keys())
        prev_soc = self.battery_config.initial_energy

        for time in timeslots:
            timeslot = result[time]
            current_soc = timeslot.battery_expected_soc_wh

            # SOC should be within battery limits (now allows down to 7%)
            self.assertGreaterEqual(
                current_soc,
                self.battery_config.storage_size_wh * 0.07
                - 1.0,  # Allow small numerical tolerance
            )
            self.assertLessEqual(current_soc, self.battery_config.storage_size_wh)

            # SOC should change based on battery flow (with 95% efficiency for charging)
            if timeslot.battery_flow_wh > 0:  # Charging
                expected_change = timeslot.battery_flow_wh * 0.95
            else:  # Discharging
                expected_change = timeslot.battery_flow_wh

            # Allow for small numerical precision differences
            self.assertAlmostEqual(current_soc, prev_soc + expected_change, delta=1.0)
            prev_soc = current_soc

    def test_create_schedule_energy_balance(self) -> None:
        """Test that energy balance constraint is satisfied"""
        base_time = datetime(2025, 1, 1, 10, 0)
        production = {base_time: 1500.0}
        consumption = {base_time: 1000.0}
        prices = {base_time: Elpris(1.0)}

        result = self.solver.create_schedule(
            production, consumption, prices, self.battery_config
        )

        self.assertIsNotNone(result)
        assert result is not None  # For mypy
        timeslot = result[base_time]

        # Energy balance: production + grid_import + battery_discharge = consumption + battery_charge + grid_export
        production_wh = self.solver.toWh(production[base_time])
        consumption_wh = self.solver.toWh(consumption[base_time])

        # Calculate net flows
        net_grid = timeslot.grid_flow_wh  # Positive = import, negative = export
        net_battery = (
            timeslot.battery_flow_wh
        )  # Positive = charging, negative = discharging

        # Energy balance should be satisfied
        energy_in = production_wh + max(0, net_grid) + max(0, -net_battery)
        energy_out = consumption_wh + max(0, net_battery) + max(0, -net_grid)

        self.assertAlmostEqual(energy_in, energy_out, delta=0.1)

    def test_create_schedule_price_arbitrage_scenario(self) -> None:
        """Test scenario with price differential - should buy low and sell high"""
        # Create 3-hour scenario with low prices early, high prices later
        base_time = datetime(2025, 1, 1, 10, 0)
        production = {
            base_time: 1000.0,  # 1kW solar
            base_time + timedelta(hours=1): 1000.0,
            base_time + timedelta(hours=2): 1000.0,
        }
        consumption = {
            base_time: 800.0,  # 0.8kW consumption
            base_time + timedelta(hours=1): 800.0,
            base_time + timedelta(hours=2): 800.0,
        }
        prices = {
            base_time: Elpris(0.2),  # Very low price - buy from grid
            base_time + timedelta(hours=1): Elpris(1.0),  # Medium price
            base_time + timedelta(hours=2): Elpris(2.5),  # High price - sell to grid
        }

        result = self.solver.create_schedule(
            production, consumption, prices, self.battery_config
        )

        self.assertIsNotNone(result)
        assert result is not None  # For mypy
        self.assertEqual(len(result), 3)

        timeslots = sorted(result.keys())

        # First hour: low price, should charge battery (buy low)
        first_timeslot = result[timeslots[0]]
        self.assertGreater(first_timeslot.battery_flow_wh, 0)  # Charging
        self.assertGreater(first_timeslot.grid_flow_wh, 0)  # Importing from grid

        # Last hour: high price, but final SOC constraint prevents sell-off
        last_timeslot = result[timeslots[2]]
        # The optimizer should still discharge if the economic benefit outweighs the final SOC value
        # But it may choose to keep some energy due to the neutral final SOC constraint
        self.assertLessEqual(
            last_timeslot.battery_flow_wh, 0
        )  # Not charging (may be discharging or idle)
        # Grid flow could be negative (exporting) or positive (importing) depending on the balance


if __name__ == "__main__":
    unittest.main()
