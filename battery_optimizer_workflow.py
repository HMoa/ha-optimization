from datetime import datetime, timedelta

from battery_config import BatteryConfig
from battery_connection import set_battery_in_state
from consumption_provider_mock import get_consumption
from elpris_api import fetch_electricity_prices
from production_provider_mock import get_production
from solver import Solver


class BatteryOptimizerWorkflow:
    def __init__(self):
        self.config = BatteryConfig.default_config()
        self.solver = Solver()
        self.schedule = None

    def run_workflow(self):
        current_slot_time = self.get_current_timeslot()
        if self.schedule is None or current_slot_time not in self.schedule.keys():
            self.generate_schedule()
        else:
            print("Schedule already exists")

        current_schedule_item = self.schedule[current_slot_time]
        if (
            abs(current_schedule_item.battery_expected_soc - self.config.initial_energy)
            > 5
        ):
            # Handle the case where the state of charge is more than 5 different from the expected value
            self.generate_schedule()
        else:
            print("Schedule is valid, executing")

        # execute the schedule item
        set_battery_in_state(current_schedule_item)

    def generate_schedule(self):
        prices = fetch_electricity_prices()

        start_date = self.get_current_timeslot()
        end_date = max(prices.keys())

        consumption = get_consumption(start_date, end_date)
        production = get_production(start_date, end_date)

        self.schedule = self.solver.create_schedule(
            production, consumption, prices, self.config
        )

        # self.run_daily(self.calculate_consumption, "00:05:00")  # Runs daily at 12:05 AM

    def get_current_timeslot(self):
        now = datetime.now().astimezone()
        start_date = now - timedelta(
            minutes=now.minute % 5,
            seconds=now.second,
            microseconds=now.microsecond,
        )

        return start_date

    def calculate_consumption(self, kwargs):
        now = datetime.now()
        start_time = (now - timedelta(days=1)).isoformat()
        end_time = now.isoformat()

        # Fetch history data
        solar_history = self.get_history(
            "sensor.solar_production", start_time=start_time, end_time=end_time
        )
        grid_history = self.get_history(
            "sensor.grid_import", start_time=start_time, end_time=end_time
        )
        battery_history = self.get_history(
            "sensor.battery_discharge", start_time=start_time, end_time=end_time
        )

        # Process data in 5-minute slots
        report = []
        time_intervals = self.generate_time_slots(
            now - timedelta(days=1), now, minutes=5
        )

        for t in time_intervals:
            solar = self.get_nearest_value(solar_history, t)
            grid = self.get_nearest_value(grid_history, t)
            battery = self.get_nearest_value(battery_history, t)

            consumption = float(grid) + float(battery) + float(solar)
            report.append({"time": t, "consumption": consumption})

        # Log or store results
        self.log("Energy Report (last 24h, 5-min slots):")
        for entry in report:
            self.log(f"{entry['time']}: {entry['consumption']} kW")

    def generate_time_slots(self, start, end, minutes=5):
        """Generate time slots in 5-minute intervals"""
        slots = []
        current = start
        while current <= end:
            slots.append(current.isoformat())
            current += timedelta(minutes=minutes)
        return slots

    def get_nearest_value(self, history_data, target_time):
        """Find the closest recorded value to the requested timestamp"""
        for state in history_data:
            for entry in state:
                if entry["last_changed"] <= target_time:
                    return entry["state"]
        return "0"  # Default if no data is found
