import os
import pickle
from datetime import datetime, timedelta

from battery_config import BatteryConfig
from battery_connection import set_battery_in_state
from consumption_provider import get_consumption
from elpris_api import fetch_electricity_prices
from production_provider import get_production
from solver import Solver


class BatteryOptimizerWorkflow:
    def __init__(self, battery_percent: int = 5):
        self.config = BatteryConfig.default_config()
        self.config.initial_energy = battery_percent * self.config.storage_size_wh / 100
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
            > 2
        ):
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

        params = [production, consumption, prices, self.config]

        sample_data_dir = os.path.join(os.path.dirname(__file__), "../sample_data")
        os.makedirs(sample_data_dir, exist_ok=True)
        sample_data_path = os.path.join(sample_data_dir, "optimizer_params.pkl")
        with open(sample_data_path, "wb") as f:
            pickle.dump(params, f)

        schedule = self.solver.create_schedule(*params)
        if schedule is None:
            print("No schedule found")
            return

        self.schedule = schedule

    def generate_schedule_from_file(self):
        sample_data_dir = os.path.join(os.path.dirname(__file__), "../sample_data")
        sample_data_path = os.path.join(sample_data_dir, "optimizer_params.pkl")
        if not os.path.exists(sample_data_path):
            print("Sample data file does not exist.")
            return None

        with open(sample_data_path, "rb") as f:
            loaded_params = pickle.load(f)

        schedule = self.solver.create_schedule(*loaded_params)
        if schedule is None:
            print("No schedule found from file data")
            return None

        self.schedule = schedule
        return schedule

    def get_current_timeslot(self):
        now = datetime.now().astimezone()
        start_date = now - timedelta(
            minutes=now.minute % 5,
            seconds=now.second,
            microseconds=now.microsecond,
        )

        return start_date

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
