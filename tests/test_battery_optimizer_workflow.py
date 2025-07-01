from __future__ import annotations

import os

# Add the parent directory to the path for imports
import sys
import unittest
from datetime import datetime
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from optimizer.battery_optimizer_workflow import BatteryOptimizerWorkflow


class TestBatteryOptimizerWorkflow(unittest.TestCase):
    def setUp(self) -> None:
        """Set up test fixtures before each test method."""
        self.workflow = BatteryOptimizerWorkflow(battery_percent=50)

    def test_init(self) -> None:
        """Test that the workflow initializes correctly."""
        self.assertEqual(self.workflow.config.storage_size_wh, 44000)
        self.assertEqual(self.workflow.config.initial_energy, 22000.0)  # 50% of 44000
        self.assertIsNone(self.workflow.schedule)
        self.assertEqual(self.workflow.solver.timeslot_length, 5)

    def test_init_with_different_battery_percent(self) -> None:
        """Test initialization with different battery percentages."""
        workflow_25 = BatteryOptimizerWorkflow(battery_percent=25)
        self.assertEqual(workflow_25.config.initial_energy, 11000.0)  # 25% of 44000

        workflow_100 = BatteryOptimizerWorkflow(battery_percent=100)
        self.assertEqual(workflow_100.config.initial_energy, 44000.0)  # 100% of 44000

    def test_get_current_timeslot(self) -> None:
        """Test that get_current_timeslot returns a properly rounded datetime."""
        now = datetime.now().astimezone()
        result = self.workflow.get_current_timeslot()

        # Should be a datetime object
        self.assertIsInstance(result, datetime)

        # Should be rounded to 5-minute intervals
        self.assertEqual(result.minute % 5, 0)
        self.assertEqual(result.second, 0)
        self.assertEqual(result.microsecond, 0)

        # Should be within 5 minutes of now
        time_diff = abs((now - result).total_seconds())
        self.assertLessEqual(time_diff, 300)  # 5 minutes in seconds

    def test_generate_schedule_no_solver_result(self) -> None:
        """Test generate_schedule when solver returns None."""
        with patch.object(self.workflow.solver, "create_schedule", return_value=None):
            self.workflow.generate_schedule()

            # Schedule should remain None
            self.assertIsNone(self.workflow.schedule)

    def test_generate_schedule_success(self) -> None:
        """Test generate_schedule when solver returns a valid schedule."""
        from optimizer.models import Activity, TimeslotItem

        mock_schedule = {
            datetime(2025, 1, 1, 10, 0, 0): TimeslotItem(
                start_time=datetime(2025, 1, 1, 10, 0, 0),
                prices=1.0,
                battery_flow=0.0,
                battery_expected_soc=22000.0,
                house_consumption=1000.0,
                activity=Activity.IDLE,
                grid_flow=0.0,
            )
        }

        with patch.object(
            self.workflow.solver, "create_schedule", return_value=mock_schedule
        ):
            with patch(
                "optimizer.battery_optimizer_workflow.fetch_electricity_prices"
            ) as mock_prices:
                with patch(
                    "optimizer.battery_optimizer_workflow.get_consumption"
                ) as mock_consumption:
                    with patch(
                        "optimizer.battery_optimizer_workflow.get_production"
                    ) as mock_production:
                        # Mock return values with real data instead of Mock objects
                        mock_prices.return_value = {datetime(2025, 1, 1, 10, 0, 0): 1.0}
                        mock_consumption.return_value = {
                            datetime(2025, 1, 1, 10, 0, 0): 1000.0
                        }
                        mock_production.return_value = {
                            datetime(2025, 1, 1, 10, 0, 0): 500.0
                        }

                        self.workflow.generate_schedule()

                        # Schedule should be set
                        self.assertEqual(self.workflow.schedule, mock_schedule)


if __name__ == "__main__":
    unittest.main()
