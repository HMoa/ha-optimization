from __future__ import annotations

import os
import pickle
from datetime import datetime, timedelta
from typing import List, Optional

from optimizer.battery_config import BatteryConfig
from optimizer.consumption_provider import (
    get_consumption_iterative,
    get_consumption_with_initial_values,
)
from optimizer.elpris_api import fetch_electricity_prices
from optimizer.models import Elpris, TimeslotItem
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

    def generate_schedule(
        self,
        initial_lag_1: Optional[float] = None,
        initial_lag_2: Optional[float] = None,
        initial_rolling_mean: Optional[float] = None,
        initial_rolling_std: Optional[float] = None,
        initial_consumption_values: Optional[List[float]] = None,
    ) -> None:
        start_date = self.get_current_timeslot()
        prices = fetch_electricity_prices(start_date)
        end_date = max(prices.keys())

        # Use the appropriate consumption method based on provided parameters
        if initial_consumption_values is not None:
            print(
                f"Using consumption prediction with {len(initial_consumption_values)} initial values"
            )
            consumption = get_consumption_with_initial_values(
                start_date, end_date, initial_consumption_values
            )
        elif any(
            param is not None
            for param in [
                initial_lag_1,
                initial_lag_2,
                initial_rolling_mean,
                initial_rolling_std,
            ]
        ):
            print("Using iterative consumption prediction with custom initial values")
            consumption = get_consumption_iterative(
                start_date,
                end_date,
                initial_lag_1=initial_lag_1,
                initial_lag_2=initial_lag_2,
                initial_rolling_mean=initial_rolling_mean,
                initial_rolling_std=initial_rolling_std,
            )
        else:
            print("Using default consumption prediction")
            from optimizer.consumption_provider import get_consumption

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

        # Reconstruct Elpris objects from the loaded data
        # The prices dictionary contains floats instead of Elpris objects after unpickling
        production, consumption, prices, config = loaded_params

        # Convert float prices back to Elpris objects
        reconstructed_prices = {}
        for time, price_value in prices.items():
            # If it's already an Elpris object, keep it
            if hasattr(price_value, "get_buy_price"):
                reconstructed_prices[time] = price_value
            else:
                # If it's a float, reconstruct the Elpris object
                # We need to estimate the spot price from the buy price
                # This is approximate since we don't have the original spot price
                estimated_spot_price = (
                    price_value - 1.03
                )  # Approximate: buy_price - (delivery_fee + energi_skatt)
                reconstructed_prices[time] = Elpris(estimated_spot_price)

        config.initial_energy = self.config.initial_energy

        schedule = self.solver.create_schedule(
            production, consumption, reconstructed_prices, config
        )
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
