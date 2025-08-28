from __future__ import annotations

from datetime import datetime
from typing import Any

from optimizer.battery_config import BatteryConfig


class EVChargingManager:
    """Manages EV charging logic and objectives for the battery optimizer."""

    def __init__(self, solver: Any) -> None:
        """Initialize the EV charging manager with a solver instance."""
        self.solver_instance = solver

    def setup_ev_variables(
        self, production_w: dict[datetime, float], battery_config: BatteryConfig
    ) -> dict[str, Any]:
        """Setup EV-related variables for the optimization problem."""
        # EV SOC variables - always present for energy balance
        ev_energy_wh = {
            i: self.solver_instance.solver.NumVar(
                0,
                (
                    battery_config.ev_max_capacity_wh
                    if battery_config.has_ev_charging()
                    else 0
                ),
                f"ev_energy_{i}",
            )
            for i in production_w.keys()
        }

        # EV charging variables - always present for energy balance (in Watts)
        ev_charge_w = {
            i: self.solver_instance.solver.NumVar(
                0,
                (
                    battery_config.ev_max_charge_speed_w
                    if battery_config.has_ev_charging()
                    else 0
                ),
                f"ev_charge_{i}",
            )
            for i in production_w.keys()
        }

        # EV deficit penalty variables - will be created only for target timeslot
        ev_deficit_wh = {}

        return {
            "ev_energy_wh": ev_energy_wh,
            "ev_charge_w": ev_charge_w,
            "ev_deficit_wh": ev_deficit_wh,
        }

    def setup_ev_charging(
        self,
        production_w: dict[datetime, float],
        battery_config: BatteryConfig,
        variables: dict[str, dict[datetime, Any]],
        initial_ev_soc_percent: float | None,
        ev_ready_time: datetime | None,
    ) -> None:
        """Setup EV charging constraints and objectives."""
        if not battery_config.has_ev_charging():
            return

        # Set initial EV SOC
        initial_ev_soc_percent = initial_ev_soc_percent or 0.0
        initial_ev_energy = (
            initial_ev_soc_percent / 100.0
        ) * battery_config.ev_max_capacity_wh

        # Setup EV SOC evolution constraints
        self._setup_ev_soc_evolution(
            production_w, battery_config, variables, initial_ev_energy
        )

        # Setup EV charging objectives if ready time is specified
        self._setup_ev_charging_objectives(
            production_w, battery_config, variables, ev_ready_time
        )

    def _setup_ev_soc_evolution(
        self,
        production_w: dict[datetime, float],
        battery_config: BatteryConfig,
        variables: dict[str, dict[datetime, Any]],
        initial_ev_energy: float,
    ) -> None:
        """Setup EV SOC evolution constraints across timeslots."""
        timeslots = list(production_w.keys())

        # First timeslot: EV energy = initial energy + charging
        if timeslots:
            first_timeslot = timeslots[0]
            self.solver_instance.solver.Add(
                variables["ev_energy_wh"][first_timeslot]
                == initial_ev_energy
                + self.solver_instance.toWh(variables["ev_charge_w"][first_timeslot])
            )

        # Subsequent timeslots: EV energy = previous energy + charging
        for i in range(1, len(timeslots)):
            current_timeslot = timeslots[i]
            previous_timeslot = timeslots[i - 1]

            self.solver_instance.solver.Add(
                variables["ev_energy_wh"][current_timeslot]
                == variables["ev_energy_wh"][previous_timeslot]
                + self.solver_instance.toWh(variables["ev_charge_w"][current_timeslot])
            )

    def _setup_ev_charging_objectives(
        self,
        production_w: dict[datetime, float],
        battery_config: BatteryConfig,
        variables: dict[str, dict[datetime, Any]],
        ev_ready_time: datetime,
    ) -> None:
        """Setup EV charging objectives based on target ready time."""
        timeslots = list(production_w.keys())
        last_timeslot = timeslots[-1]
        first_timeslot = timeslots[0]

        # Find the timeslot closest to ready time
        target_timeslot = None
        for timeslot in timeslots:
            if timeslot >= ev_ready_time:
                target_timeslot = timeslot
                break

        # If no timeslot is after the ready time, use the last timeslot
        if target_timeslot is None:
            target_timeslot = last_timeslot

        # Check if ready time is within current scheduling period
        if ev_ready_time <= last_timeslot:
            # Target is within period - charge to full at ready time
            target_soc_percent = 100.0  # Charge to full
            max_price = battery_config.ev_max_charge_price_kr_per_kwh
        else:
            # Target is outside period - scale target and price based on time progress
            total_time_to_target = (
                ev_ready_time - first_timeslot
            ).total_seconds() / 3600  # hours
            elapsed_time = (
                last_timeslot - first_timeslot
            ).total_seconds() / 3600  # hours

            if total_time_to_target > 0:
                progress_percentage = elapsed_time / total_time_to_target
                target_soc_percent = min(
                    100.0, progress_percentage * 100.0
                )  # Scale target to full
                max_price = (
                    battery_config.ev_max_charge_price_kr_per_kwh * progress_percentage
                )
            else:
                # Fallback if time calculation fails
                target_soc_percent = 100.0
                max_price = battery_config.ev_max_charge_price_kr_per_kwh

        # Create EV deficit variable only for the target timeslot
        target_soc_wh = (target_soc_percent / 100.0) * battery_config.ev_max_capacity_wh
        variables["ev_deficit_wh"][target_timeslot] = (
            self.solver_instance.solver.NumVar(
                0,
                self.solver_instance.solver.infinity(),
                f"ev_deficit_{target_timeslot}",
            )
        )

        # Add constraint: ev_deficit_wh >= max(0, target_soc_wh - ev_energy_wh)
        self.solver_instance.solver.Add(
            variables["ev_deficit_wh"][target_timeslot]
            >= target_soc_wh - variables["ev_energy_wh"][target_timeslot]
        )
        self.solver_instance.solver.Add(
            variables["ev_deficit_wh"][target_timeslot] >= 0
        )

        # Add penalty for EV deficit at target time (max_price per kWh)
        self.solver_instance.solver.Objective().SetCoefficient(
            variables["ev_deficit_wh"][target_timeslot], max_price
        )

    def populate_ev_data(
        self,
        variables: dict[str, dict[datetime, Any]],
        battery_config: BatteryConfig,
        timeslot: datetime,
    ) -> tuple[float, float]:
        """Populate EV energy and SOC data for a timeslot."""
        if not battery_config.has_ev_charging():
            return 0.0, 0.0

        ev_energy = variables["ev_energy_wh"][timeslot].solution_value()
        ev_soc_percent = (ev_energy / battery_config.ev_max_capacity_wh) * 100.0

        return ev_energy, ev_soc_percent
