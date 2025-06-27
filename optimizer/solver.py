from datetime import datetime
from typing import Dict, Optional

from battery_config import BatteryConfig
from models import Activity, Elpris, TimeslotItem
from ortools.linear_solver import pywraplp


class Solver:
    def __init__(self, timeslot_length: int):
        self.solver = None
        self.timeslot_length = timeslot_length

    def toWh(self, value: float) -> float:
        return value * (self.timeslot_length / 60)

    def create_schedule(
        self,
        production_w: Dict[datetime, float],
        consumption_w: Dict[datetime, float],
        prices: Dict[datetime, Elpris],
        battery_config: BatteryConfig,
    ) -> Optional[Dict[datetime, TimeslotItem]]:
        eta_c = 0.95
        battery_min = battery_config.storage_size_wh * 0.3

        # Create the linear solver with the GLOP backend.
        self.solver = pywraplp.Solver.CreateSolver("GLOP")
        if not self.solver:
            return None

        # Create variables for each time-slot
        time_slots = len(production_w)
        if time_slots == 0 or len(consumption_w) != time_slots:
            return None

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
                battery_min, battery_config.storage_size_wh, f"battery_energy_{i}"
            )
            for i in production_w.keys()
        }
        is_charging_or_discharging = {
            i: self.solver.BoolVar(f"is_charging_or_discharging_{i}")
            for i in production_w.keys()
        }

        # Initial energy in the battery
        initial_energy = battery_config.initial_energy
        print(f"Initial energy solver: {initial_energy}")

        # Constraints
        previous_key = None
        for i in production_w.keys():

            # Energy balance constraint
            self.solver.Add(
                self.toWh(production_w[i]) + grid_import_wh[i] + battery_discharge_wh[i]
                == self.toWh(consumption_w[i])
                + battery_charge_wh[i]
                + grid_export_wh[i]
            )

            # Battery state update constraint. Make sure the charge and discharge drains the battery for the next timeslot.
            if previous_key is None:
                self.solver.Add(
                    battery_energy_wh[i]
                    == initial_energy
                    + (eta_c * battery_charge_wh[i])
                    - (battery_discharge_wh[i])
                )
            else:
                self.solver.Add(
                    battery_energy_wh[i]
                    == battery_energy_wh[previous_key]
                    + (eta_c * battery_charge_wh[i])
                    - (battery_discharge_wh[i])
                )

            # Ensure that charging and discharging cannot happen simultaneously
            self.solver.Add(
                battery_charge_wh[i]
                <= self.toWh(battery_config.max_charge_speed_w)
                * is_charging_or_discharging[i]
            )
            self.solver.Add(
                battery_discharge_wh[i]
                <= self.toWh(battery_config.max_discharge_speed_w)
                * (1 - is_charging_or_discharging[i])
            )

            previous_key = i

        # Objective: minimize the cost of grid import
        objective = self.solver.Objective()
        for i in production_w.keys():
            objective.SetCoefficient(
                grid_import_wh[i], prices[get_closest_price_timeslot(i)].get_buy_price()
            )
            objective.SetCoefficient(
                grid_export_wh[i],
                -prices[get_closest_price_timeslot(i)].get_sell_price(),
            )
            objective.SetCoefficient(battery_charge_wh[i], 0.01)  # Penalty for charging
        objective.SetMinimization()

        result = self.solver.Solve()
        if result != pywraplp.Solver.OPTIMAL and result != pywraplp.Solver.FEASIBLE:
            return None

        schedule = {}
        for i in production_w.keys():
            need = self.toWh(consumption_w[i] - production_w[i])
            flow = (
                battery_charge_wh[i].solution_value()
                - battery_discharge_wh[i].solution_value()
            )

            if flow > 1:
                if flow <= need + 1:
                    schedule[i] = TimeslotItem(
                        start_time=i,
                        prices=prices[get_closest_price_timeslot(i)].get_spot_price(),
                        battery_flow=flow,
                        battery_expected_soc=battery_energy_wh[i].solution_value(),
                        house_consumption=need,
                        activity=Activity.SELF_CONSUMPTION,
                    )
                else:
                    schedule[i] = TimeslotItem(
                        start_time=i,
                        prices=prices[get_closest_price_timeslot(i)].get_spot_price(),
                        battery_flow=flow,
                        battery_expected_soc=battery_energy_wh[i].solution_value(),
                        house_consumption=need,
                        activity=Activity.CHARGE,
                        amount=flow,
                    )

            elif flow < -1:
                if -flow <= need + 1:
                    schedule[i] = TimeslotItem(
                        start_time=i,
                        prices=prices[get_closest_price_timeslot(i)].get_spot_price(),
                        battery_flow=flow,
                        battery_expected_soc=battery_energy_wh[i].solution_value(),
                        house_consumption=need,
                        activity=Activity.SELF_CONSUMPTION,
                        amount=flow,
                    )

                else:
                    schedule[i] = TimeslotItem(
                        start_time=i,
                        prices=prices[get_closest_price_timeslot(i)].get_spot_price(),
                        battery_flow=flow,
                        battery_expected_soc=battery_energy_wh[i].solution_value(),
                        house_consumption=need,
                        activity=Activity.DISCHARGE,
                    )

            else:
                schedule[i] = TimeslotItem(
                    start_time=i,
                    prices=prices[get_closest_price_timeslot(i)].get_spot_price(),
                    battery_flow=flow,
                    battery_expected_soc=battery_energy_wh[i].solution_value(),
                    house_consumption=need,
                    activity=Activity.IDLE,
                )

        return schedule


def get_closest_price_timeslot(time: datetime) -> datetime:
    return time.replace(minute=0, second=0, microsecond=0)
