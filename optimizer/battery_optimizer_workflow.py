from __future__ import annotations

import os
import pickle
from datetime import datetime, timedelta

from optimizer.battery_config import BatteryConfig
from optimizer.consumption_provider import get_consumption
from optimizer.elpris_api import fetch_electricity_prices
from optimizer.models import TimeslotItem
from optimizer.production_provider import get_production
from optimizer.solver import Solver


class BatteryOptimizerWorkflow:
    def __init__(self, battery_percent: int) -> None:
        self.config = BatteryConfig.default_config()
        self.config.initial_energy = float(
            battery_percent * self.config.storage_size_wh / 100
        )
        print(
            f"Initial energy: {self.config.initial_energy} and percent: {battery_percent}"
        )
        self.solver = Solver(timeslot_length=5)
        self.schedule: dict[datetime, TimeslotItem] | None = None

    def generate_schedule(self) -> None:
        start_date = self.get_current_timeslot()
        prices = fetch_electricity_prices(start_date)
        end_date = max(prices.keys())

        consumption = get_consumption(start_date, end_date)
        production = get_production(start_date, end_date)

        schedule = self.solver.create_schedule(
            production, consumption, prices, self.config
        )
        if schedule is None:
            print("No schedule found")
            return

        # Save params for later use
        params = [production, consumption, prices, self.config]
        sample_data_dir = os.path.join(os.path.dirname(__file__), "../sample_data")
        os.makedirs(sample_data_dir, exist_ok=True)
        sample_data_path = os.path.join(sample_data_dir, "optimizer_params.pkl")
        with open(sample_data_path, "wb") as f:
            pickle.dump(params, f)

        self.schedule = schedule

    def generate_schedule_from_file(self) -> dict[datetime, TimeslotItem] | None:
        sample_data_dir = os.path.join(os.path.dirname(__file__), "../sample_data")
        sample_data_path = os.path.join(sample_data_dir, "optimizer_params.pkl")
        if not os.path.exists(sample_data_path):
            print("Sample data file does not exist.")
            return None

        with open(sample_data_path, "rb") as f:
            loaded_params = pickle.load(f)

        loaded_params[3].initial_energy = self.config.initial_energy

        schedule = self.solver.create_schedule(*loaded_params)
        if schedule is None:
            print("No schedule found from file data")
            return None

        self.schedule = schedule
        return schedule

    def get_current_timeslot(self) -> datetime:
        now = datetime.now().astimezone()
        start_date = now - timedelta(
            minutes=now.minute % 5,
            seconds=now.second,
            microseconds=now.microsecond,
        )

        return start_date
