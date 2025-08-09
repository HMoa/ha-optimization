from __future__ import annotations

import os
import pickle
from datetime import datetime, timedelta

from optimizer.battery_config import BatteryConfig
from optimizer.consumption_provider import get_consumption_with_initial_values
from optimizer.elpris_api import fetch_electricity_prices
from optimizer.influxdb_client import get_initial_consumption_values
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
    ) -> None:
        start_date = self.get_current_timeslot()
        prices = fetch_electricity_prices(start_date, self.config.grid_area)

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
            self._extend_prices_with_mean(prices)

        end_date = max(prices.keys()) + timedelta(hours=1) - timedelta(minutes=5)

        influx_values = get_initial_consumption_values()

        print("Creating predictions")
        consumption = get_consumption_with_initial_values(
            start_date, end_date, influx_values
        )
        production = get_production(start_date, end_date)
        print("Done creating predictions")

        schedule = self.solver.create_schedule(
            production, consumption, prices, self.config
        )
        if schedule is None:
            print("No schedule found")
            return

        self.schedule = schedule

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

        # Create a simple self-consumption schedule
        schedule: dict[datetime, TimeslotItem] = {}
        current_energy = self.config.initial_energy

        # Iterate through 5-minute time slots
        current_time = start_date
        while current_time < end_date:
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
                house_consumption_wh=0,
                activity=Activity.SELF_CONSUMPTION,
                grid_flow_wh=0,
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
