from datetime import datetime
from typing import Dict, Optional

from ortools.linear_solver import pywraplp

from battery_config import BatteryConfig
from models import Activity, Elpris, TimeslotItem


class Solver:
    def __init__(self):
        self.solver = None

    def create_schedule(
        self,
        production: Dict[datetime, float],
        consumption: Dict[datetime, float],
        prices: Dict[datetime, Elpris],
        battery_config: BatteryConfig,
    ) -> Optional[Dict[datetime, TimeslotItem]]:
        eta_c = 0.95

        # Create the linear solver with the GLOP backend.
        self.solver = pywraplp.Solver.CreateSolver("GLOP")
        if not self.solver:
            return None

        # Create variables for each time-slot
        time_slots = len(production)
        if time_slots == 0 or len(consumption) != time_slots:
            return None

        grid_import = {
            i: self.solver.NumVar(0, self.solver.infinity(), f"grid_import_{i}")
            for i in production.keys()
        }
        grid_export = {
            i: self.solver.NumVar(0, self.solver.infinity(), f"grid_export_{i}")
            for i in production.keys()
        }
        battery_charge = {
            i: self.solver.NumVar(
                0, battery_config.max_charge_speed_w, f"battery_charge_{i}"
            )
            for i in production.keys()
        }
        battery_discharge = {
            i: self.solver.NumVar(
                0, battery_config.max_discharge_speed_w, f"battery_discharge_{i}"
            )
            for i in production.keys()
        }
        battery_energy = {
            i: self.solver.NumVar(
                0, battery_config.storage_size_wh, f"battery_energy_{i}"
            )
            for i in production.keys()
        }
        is_charging_or_discharging = {
            i: self.solver.BoolVar(f"is_charging_or_discharging_{i}")
            for i in production.keys()
        }

        # Initial energy in the battery
        initial_energy = battery_config.initial_energy

        # Constraints
        previous_key = None
        for i in production.keys():

            # Energy balance constraint
            self.solver.Add(
                (production[i] * 12) + grid_import[i] + battery_discharge[i]
                == (consumption[i] * 12) + battery_charge[i] + grid_export[i]
            )

            # Battery state update constraint. Make sure the charge and discharge drains the battery for the next timeslot.
            if previous_key is None:
                self.solver.Add(
                    battery_energy[i]
                    == initial_energy
                    + (eta_c * battery_charge[i] / 12)
                    - (battery_discharge[i] / 12)
                )
            else:
                self.solver.Add(
                    battery_energy[i]
                    == battery_energy[previous_key]
                    + (eta_c * battery_charge[i] / 12)
                    - (battery_discharge[i] / 12)
                )

            # Ensure that charging and discharging cannot happen simultaneously
            self.solver.Add(
                battery_charge[i]
                <= battery_config.max_charge_speed_w * is_charging_or_discharging[i]
            )
            self.solver.Add(
                battery_discharge[i]
                <= battery_config.max_discharge_speed_w
                * (1 - is_charging_or_discharging[i])
            )

            previous_key = i

        # Objective: minimize the cost of grid import
        objective = self.solver.Objective()
        for i in production.keys():
            objective.SetCoefficient(
                grid_import[i], prices[get_closest_price_timeslot(i)].get_buy_price()
            )
            objective.SetCoefficient(
                grid_export[i], -prices[get_closest_price_timeslot(i)].get_sell_price()
            )
            objective.SetCoefficient(battery_charge[i], 0.01)  # Penalty for charging
        objective.SetMinimization()

        result = self.solver.Solve()
        if result != pywraplp.Solver.OPTIMAL and result != pywraplp.Solver.FEASIBLE:
            return None

        schedule = {}
        for i in production.keys():
            need = (consumption[i] - production[i]) * 12
            flow = (
                battery_charge[i].solution_value()
                - battery_discharge[i].solution_value()
            )

            if flow > 1:
                if flow <= need:
                    schedule[i] = TimeslotItem(
                        start_time=i,
                        prices=prices[get_closest_price_timeslot(i)].get_spot_price(),
                        battery_flow=flow,
                        battery_expected_soc=battery_energy[i].solution_value(),
                        activity=Activity.SELF_CONSUMPTION,
                    )
                else:
                    schedule[i] = TimeslotItem(
                        start_time=i,
                        prices=prices[get_closest_price_timeslot(i)].get_spot_price(),
                        battery_flow=flow,
                        battery_expected_soc=battery_energy[i].solution_value(),
                        activity=Activity.CHARGE,
                        amount=flow,
                    )

            elif flow < -1:
                if -flow <= need:
                    schedule[i] = TimeslotItem(
                        start_time=i,
                        prices=prices[get_closest_price_timeslot(i)].get_spot_price(),
                        battery_flow=flow,
                        battery_expected_soc=battery_energy[i].solution_value(),
                        activity=Activity.DISCHARGE,
                        amount=flow,
                    )

                else:
                    schedule[i] = TimeslotItem(
                        start_time=i,
                        prices=prices[get_closest_price_timeslot(i)].get_spot_price(),
                        battery_flow=flow,
                        battery_expected_soc=battery_energy[i].solution_value(),
                        activity=Activity.SELF_CONSUMPTION,
                    )

            else:
                schedule[i] = TimeslotItem(
                    start_time=i,
                    prices=prices[get_closest_price_timeslot(i)].get_spot_price(),
                    battery_flow=flow,
                    battery_expected_soc=battery_energy[i].solution_value(),
                    activity=Activity.IDLE,
                )

        return schedule


def get_closest_price_timeslot(time: datetime) -> datetime:
    return time.replace(minute=0, second=0, microsecond=0)
