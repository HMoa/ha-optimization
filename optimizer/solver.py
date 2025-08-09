# mypy: ignore-errors

from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from ortools.linear_solver import pywraplp  # type: ignore

from optimizer.battery_config import BatteryConfig
from optimizer.models import Activity, Elpris, TimeslotItem


class Solver:
    def __init__(self, timeslot_length: int):
        self.solver = None
        self.timeslot_length = timeslot_length

    def toWh(self, value: float) -> float:
        return value * (self.timeslot_length / 60)

    def _setup_variables(
        self,
        production_w: dict[datetime, float],
        battery_config: BatteryConfig,
    ) -> dict[str, dict[datetime, Any]]:
        """Setup all optimization variables."""
        grid_import_wh = {
            i: self.solver.NumVar(0, self.solver.infinity(), f"grid_import_{i}")
            for i in production_w.keys()
        }
        grid_export_wh = {
            i: self.solver.NumVar(0, self.solver.infinity(), f"grid_export_{i}")
            for i in production_w.keys()
        }
        battery_charge_wh = {
            i: self.solver.NumVar(
                0, battery_config.max_charge_speed_w, f"battery_charge_{i}"
            )
            for i in production_w.keys()
        }
        battery_discharge_wh = {
            i: self.solver.NumVar(
                0, battery_config.max_discharge_speed_w, f"battery_discharge_{i}"
            )
            for i in production_w.keys()
        }
        battery_energy_wh = {
            i: self.solver.NumVar(
                battery_config.storage_size_wh * 0.07,  # Allow down to 7%
                battery_config.storage_size_wh,
                f"battery_energy_{i}",
            )
            for i in production_w.keys()
        }
        is_charging_or_discharging = {
            i: self.solver.BoolVar(f"is_charging_or_discharging_{i}")
            for i in production_w.keys()
        }
        # SOC deficit penalty variables
        soc_deficit_wh = {
            i: self.solver.NumVar(0, self.solver.infinity(), f"soc_deficit_{i}")
            for i in production_w.keys()
        }

        return {
            "grid_import_wh": grid_import_wh,
            "grid_export_wh": grid_export_wh,
            "battery_charge_wh": battery_charge_wh,
            "battery_discharge_wh": battery_discharge_wh,
            "battery_energy_wh": battery_energy_wh,
            "is_charging_or_discharging": is_charging_or_discharging,
            "soc_deficit_wh": soc_deficit_wh,
        }

    def _setup_constraints(
        self,
        production_w: dict[datetime, float],
        consumption_w: dict[datetime, float],
        battery_config: BatteryConfig,
        variables: dict[str, dict[datetime, Any]],
    ) -> None:
        """Setup all optimization constraints."""
        eta_c = 0.95
        initial_energy = battery_config.initial_energy
        target_soc_wh = battery_config.storage_size_wh * 0.3  # 30% target SOC

        previous_key = None
        for i in production_w.keys():
            # Energy balance constraint
            self.solver.Add(
                self.toWh(production_w[i])
                + variables["grid_import_wh"][i]
                + variables["battery_discharge_wh"][i]
                == self.toWh(consumption_w[i])
                + variables["battery_charge_wh"][i]
                + variables["grid_export_wh"][i]
            )

            # Battery state update constraint. Make sure the charge and discharge drains the battery for the next timeslot.
            if previous_key is None:
                self.solver.Add(
                    variables["battery_energy_wh"][i]
                    == initial_energy
                    + (eta_c * variables["battery_charge_wh"][i])
                    - (variables["battery_discharge_wh"][i])
                )
            else:
                self.solver.Add(
                    variables["battery_energy_wh"][i]
                    == variables["battery_energy_wh"][previous_key]
                    + (eta_c * variables["battery_charge_wh"][i])
                    - (variables["battery_discharge_wh"][i])
                )

            # Ensure that charging and discharging cannot happen simultaneously
            self.solver.Add(
                variables["battery_charge_wh"][i]
                <= self.toWh(battery_config.max_charge_speed_w)
                * variables["is_charging_or_discharging"][i]
            )
            self.solver.Add(
                variables["battery_discharge_wh"][i]
                <= self.toWh(battery_config.max_discharge_speed_w)
                * (1 - variables["is_charging_or_discharging"][i])
            )

            # SOC deficit constraint: soc_deficit_wh >= max(0, target_soc - battery_energy_wh)
            # This creates a soft constraint that penalizes going below 30% SOC
            self.solver.Add(
                variables["soc_deficit_wh"][i]
                >= target_soc_wh - variables["battery_energy_wh"][i]
            )
            self.solver.Add(variables["soc_deficit_wh"][i] >= 0)

            previous_key = i

    def _setup_objective(
        self,
        production_w: dict[datetime, float],
        prices: dict[datetime, Elpris],
        variables: dict[str, dict[datetime, Any]],
    ) -> None:
        """Setup the optimization objective."""
        objective = self.solver.Objective()
        soc_penalty_coefficient = 0.1  # Penalty per Wh below 30% SOC

        for i in production_w.keys():
            objective.SetCoefficient(
                variables["grid_import_wh"][i],
                prices[get_closest_price_timeslot(i)].get_buy_price(),
            )
            objective.SetCoefficient(
                variables["grid_export_wh"][i],
                -prices[get_closest_price_timeslot(i)].get_sell_price(),
            )
            objective.SetCoefficient(
                variables["battery_charge_wh"][i], 0.01
            )  # Penalty for charging
            objective.SetCoefficient(
                variables["soc_deficit_wh"][i], soc_penalty_coefficient
            )  # Penalty for low SOC

            objective.SetCoefficient(
                variables["battery_energy_wh"][i], -0.001
            )  # Miniscule soc bonus, to favour leaving discharge to end of period instead of randomly in the middle

        # Add neutral final SOC value to prevent end-of-horizon sell-off
        final_key = list(production_w.keys())[-1]
        final_sell_price = prices[
            get_closest_price_timeslot(final_key)
        ].get_sell_price()
        objective.SetCoefficient(
            variables["battery_energy_wh"][final_key], -final_sell_price
        )

        objective.SetMinimization()

    def _create_schedule(
        self,
        production_w: dict[datetime, float],
        consumption_w: dict[datetime, float],
        prices: dict[datetime, Elpris],
        battery_config: BatteryConfig,
        variables: dict[str, dict[datetime, Any]],
    ) -> dict[datetime, TimeslotItem]:
        """Create the final schedule from the solved variables."""
        schedule = {}
        for i in production_w.keys():
            need = self.toWh(consumption_w[i] - production_w[i])
            battery_flow = (
                variables["battery_charge_wh"][i].solution_value()
                - variables["battery_discharge_wh"][i].solution_value()
            )
            grid_flow = (
                variables["grid_import_wh"][i].solution_value()
                - variables["grid_export_wh"][i].solution_value()
            )

            pris = prices[get_closest_price_timeslot(i)].get_spot_price()
            expected_soc = variables["battery_energy_wh"][i].solution_value()
            expected_soc_percent = (expected_soc / battery_config.storage_size_wh) * 100
            timeslot = TimeslotItem(
                start_time=i,
                prices=pris,
                battery_flow_wh=battery_flow,
                battery_expected_soc_wh=expected_soc,
                battery_expected_soc_percent=expected_soc_percent,
                house_consumption_wh=need,
                activity=Activity.CHARGE_LIMIT,
                amount=battery_flow * (60 / self.timeslot_length),  # Convert Wh to W
                grid_flow_wh=grid_flow,
            )

            schedule[i] = timeslot

            if battery_flow > 1:
                if (
                    battery_flow <= -need - 10
                ):  # We are storing less than we create. Limit the charge.
                    timeslot.activity = Activity.CHARGE_LIMIT

                elif battery_flow < -need + 5:  # We are storing all we create.
                    timeslot.activity = Activity.CHARGE_SOLAR_SURPLUS

                else:  # We are storing more than we create. Charge from grid.
                    timeslot.activity = Activity.CHARGE

            elif battery_flow < -1:
                if (
                    -battery_flow <= need - 10
                ):  # We are using less battery than the house requires. Limit the discharge.
                    timeslot.activity = Activity.DISCHARGE_LIMIT

                elif (
                    -battery_flow <= need + 5
                ):  # We are using battery to fullfill the house's needs.
                    timeslot.activity = Activity.DISCHARGE_FOR_HOME

                else:  # We are discharging more battery than the house requires. Sell to the grid.
                    timeslot.activity = Activity.DISCHARGE

            else:  # If we don't currently have any flow, but the predictions are inacurate. What is the intention?
                if (
                    grid_flow > 0
                ):  # We are buying from the grid, so charge solar since it's cheap.
                    timeslot.activity = Activity.CHARGE_SOLAR_SURPLUS
                elif (
                    grid_flow < 0
                ):  # We are selling to the grid, so discharge for home since it's expensive.
                    timeslot.activity = Activity.DISCHARGE_FOR_HOME

        return schedule

    def create_schedule(
        self,
        production_w: dict[datetime, float],
        consumption_w: dict[datetime, float],
        prices: dict[datetime, Elpris],
        battery_config: BatteryConfig,
    ) -> dict[datetime, TimeslotItem] | None:  # type: ignore
        # Create the linear solver with the GLOP backend.
        self.solver = cast(Any, pywraplp.Solver.CreateSolver("GLOP"))
        if not self.solver:
            return None

        # Validate input
        time_slots = len(production_w)
        if time_slots == 0 or len(consumption_w) != time_slots:
            return None

        # Setup variables
        variables = self._setup_variables(production_w, battery_config)

        # Setup constraints
        self._setup_constraints(production_w, consumption_w, battery_config, variables)

        # Setup objective
        self._setup_objective(production_w, prices, variables)

        print("Solving... ")
        result = self.solver.Solve()
        print("Solved with status: ", result)

        if result != pywraplp.Solver.OPTIMAL and result != pywraplp.Solver.FEASIBLE:
            return None

        # Create schedule
        return self._create_schedule(
            production_w, consumption_w, prices, battery_config, variables
        )


def get_closest_price_timeslot(time: datetime) -> datetime:
    return time.replace(minute=0, second=0, microsecond=0)
