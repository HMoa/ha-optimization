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
from optimizer.models import Activity, Elpris, TimeslotItem
from optimizer.production_provider import get_production
from optimizer.solver import Solver


class BatteryOptimizerWorkflow:
    def __init__(self, battery_percent: float) -> None:
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

        # Handle cases where we don't have enough price data
        current_hour = start_date.hour

        # If prices is empty, check if it's before 17:00
        if len(prices) == 0:
            if current_hour < 17:
                print(
                    "No prices available and it's before 17:00. Exiting to wait for prices to come back online."
                )
                return
            else:
                print(
                    "No prices available after 17:00. Creating self-consumption schedule for next 24 hours."
                )
                self._create_self_consumption_schedule(start_date)
                return

        # If we have too few prices (less than 7 hours after 17:00),
        # extend with mean price to artificially extent the horizon to optimize for.
        # We might find a better way to disincentivize selling off all the energy at the end of the day.
        if len(prices) < (24 - 17):
            print(
                f"Only {len(prices)} prices available, extending with mean price for next 24 hours."
            )
            self._extend_prices_with_mean(prices)

        end_date = max(prices.keys())
        print(f"Dates: {start_date} - {end_date}")

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

        print(f"Production slots: {len(production)} - {len(consumption)}")

        schedule = self.solver.create_schedule(
            production, consumption, prices, self.config
        )
        if schedule is None:
            print("No schedule found")
            return

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

    def _create_self_consumption_schedule(self, start_date: datetime) -> None:
        """Create a self-consumption only schedule for the next 24 hours."""
        from datetime import timedelta

        # Create a 24-hour schedule with self-consumption only
        end_date = start_date + timedelta(hours=24)

        # Get consumption and production data
        consumption = get_consumption_iterative(start_date, end_date)
        production = get_production(start_date, end_date)

        # Create a simple self-consumption schedule
        schedule: dict[datetime, TimeslotItem] = {}
        current_energy = self.config.initial_energy

        # Iterate through 5-minute time slots
        current_time = start_date
        while current_time < end_date:
            # Get consumption and production for this time slot
            net_consumption = consumption.get(current_time, 0.0)
            net_production = production.get(current_time, 0.0)

            # Create timeslot item
            schedule[current_time] = TimeslotItem(
                start_time=current_time,
                prices=0.0,  # No price data available
                battery_flow_wh=0,
                battery_expected_soc_wh=current_energy,
                battery_expected_soc_percent=(
                    current_energy / self.config.storage_size_wh
                )
                * 100,
                house_consumption_wh=net_consumption,
                activity=Activity.SELF_CONSUMPTION,
                grid_flow_wh=net_production - net_consumption,
                amount=0,
            )

            # Move to next 5-minute slot
            current_time += timedelta(minutes=5)

        self.schedule = schedule
        print("Self-consumption schedule created successfully.")

    def _extend_prices_with_mean(self, prices: dict[datetime, Elpris]) -> None:
        """Extend the prices dictionary with mean prices for the next 24 hours."""
        from datetime import timedelta

        if not prices:
            return

        # Calculate mean spot price from available prices
        spot_prices = [price.get_spot_price() for price in prices.values()]
        mean_spot_price = sum(spot_prices) / len(spot_prices)

        # Create mean price object
        mean_price = Elpris(mean_spot_price)

        # Find the latest time in current prices
        latest_time = max(prices.keys())

        # Extend prices for the next 24 hours
        current_time = latest_time + timedelta(minutes=60)
        end_time = latest_time + timedelta(hours=24)

        while current_time <= end_time:
            if current_time not in prices:
                prices[current_time] = mean_price
            current_time += timedelta(minutes=60)

        print(f"Extended prices with mean spot price of {mean_spot_price:.2f} kr/kWh")
