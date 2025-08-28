from __future__ import annotations

import os
import sys
import unittest

# Add the optimizer directory to the path so we can import the BatteryConfig class
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "optimizer"))

from optimizer.battery_config import BatteryConfig


class TestBatteryConfig(unittest.TestCase):
    def test_battery_config_with_ev_parameters(self) -> None:
        """Test that BatteryConfig correctly handles EV charging parameters when provided."""
        config = BatteryConfig(
            grid_area="SE3",
            storage_size_wh=44000,
            initial_energy=1000.0,
            max_charge_speed_w=8000,
            max_discharge_speed_w=9000,
            ev_max_capacity_wh=75000,  # 75 kWh EV battery
            ev_max_charge_speed_w=11000,  # 11 kW EV charger
        )

        self.assertEqual(config.get_grid_area(), "SE3")
        self.assertEqual(config.get_storage_size_wh(), 44000)
        self.assertEqual(config.get_ev_max_capacity_wh(), 75000)
        self.assertEqual(config.get_ev_max_charge_speed_w(), 11000)
        self.assertTrue(config.has_ev_charging())

    def test_battery_config_without_ev_parameters(self) -> None:
        """Test that BatteryConfig correctly handles missing EV charging parameters."""
        config = BatteryConfig(
            grid_area="SE3",
            storage_size_wh=44000,
            initial_energy=1000.0,
            max_charge_speed_w=8000,
            max_discharge_speed_w=9000,
            ev_max_capacity_wh=None,
            ev_max_charge_speed_w=None,
        )

        self.assertIsNone(config.get_ev_max_capacity_wh())
        self.assertIsNone(config.get_ev_max_charge_speed_w())
        self.assertFalse(config.has_ev_charging())

    def test_battery_config_partial_ev_parameters(self) -> None:
        """Test that BatteryConfig correctly handles partial EV charging parameters."""
        # Test with only capacity set
        config_capacity_only = BatteryConfig(
            grid_area="SE3",
            storage_size_wh=44000,
            initial_energy=1000.0,
            max_charge_speed_w=8000,
            max_discharge_speed_w=9000,
            ev_max_capacity_wh=75000,
            ev_max_charge_speed_w=None,
        )
        self.assertFalse(config_capacity_only.has_ev_charging())

        # Test with only charge speed set
        config_speed_only = BatteryConfig(
            grid_area="SE3",
            storage_size_wh=44000,
            initial_energy=1000.0,
            max_charge_speed_w=8000,
            max_discharge_speed_w=9000,
            ev_max_capacity_wh=None,
            ev_max_charge_speed_w=11000,
        )
        self.assertFalse(config_speed_only.has_ev_charging())

    def test_default_config_loading(self) -> None:
        """Test that default config loading works with EV parameters."""
        config = BatteryConfig.default_config()

        # Should have basic parameters
        self.assertEqual(config.get_grid_area(), "SE3")
        self.assertEqual(config.get_storage_size_wh(), 44000)
        self.assertEqual(config.get_max_charge_speed_w(), 8000)
        self.assertEqual(config.get_max_discharge_speed_w(), 9000)

        # EV parameters should be None from config file
        self.assertIsNone(config.get_ev_max_capacity_wh())
        self.assertIsNone(config.get_ev_max_charge_speed_w())
        self.assertFalse(config.has_ev_charging())

    def test_ev_charging_detection(self) -> None:
        """Test that has_ev_charging() correctly detects when EV charging is configured."""
        # Both parameters set
        config_full = BatteryConfig(
            grid_area="SE3",
            storage_size_wh=44000,
            initial_energy=1000.0,
            max_charge_speed_w=8000,
            max_discharge_speed_w=9000,
            ev_max_capacity_wh=75000,
            ev_max_charge_speed_w=11000,
        )
        self.assertTrue(config_full.has_ev_charging())

        # No parameters set
        config_none = BatteryConfig(
            grid_area="SE3",
            storage_size_wh=44000,
            initial_energy=1000.0,
            max_charge_speed_w=8000,
            max_discharge_speed_w=9000,
        )
        self.assertFalse(config_none.has_ev_charging())

        # Zero values (edge case)
        config_zero = BatteryConfig(
            grid_area="SE3",
            storage_size_wh=44000,
            initial_energy=1000.0,
            max_charge_speed_w=8000,
            max_discharge_speed_w=9000,
            ev_max_capacity_wh=0,
            ev_max_charge_speed_w=0,
        )
        self.assertTrue(config_zero.has_ev_charging())  # 0 is not None


if __name__ == "__main__":
    unittest.main()
