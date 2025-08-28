from __future__ import annotations

import json
import os
from typing import Any


class BatteryConfig:
    def __init__(
        self,
        grid_area: str,
        storage_size_wh: int,
        initial_energy: float,
        max_charge_speed_w: int,
        max_discharge_speed_w: int,
        ev_max_capacity_wh: int | None = None,
        ev_max_charge_speed_w: int | None = None,
        ev_max_charge_price_kr_per_kwh: float = 0.8,
        fuse_capacity_w: int = 11000,
    ) -> None:
        self.grid_area: str = grid_area
        self.storage_size_wh: int = storage_size_wh
        self.initial_energy: float = initial_energy
        self.max_charge_speed_w: int = max_charge_speed_w
        self.max_discharge_speed_w: int = max_discharge_speed_w
        self.ev_max_capacity_wh: int | None = ev_max_capacity_wh
        self.ev_max_charge_speed_w: int | None = ev_max_charge_speed_w
        self.ev_max_charge_price_kr_per_kwh: float = ev_max_charge_price_kr_per_kwh
        self.fuse_capacity_w: int = fuse_capacity_w

    def get_grid_area(self) -> str:
        return self.grid_area

    def get_storage_size_wh(self) -> int:
        return self.storage_size_wh

    def get_initial_energy(self) -> float:
        return self.initial_energy

    def get_max_charge_speed_w(self) -> int:
        return self.max_charge_speed_w

    def get_max_discharge_speed_w(self) -> int:
        return self.max_discharge_speed_w

    def get_ev_max_capacity_wh(self) -> int | None:
        return self.ev_max_capacity_wh

    def get_ev_max_charge_speed_w(self) -> int | None:
        return self.ev_max_charge_speed_w

    def get_ev_max_charge_price_kr_per_kwh(self) -> float:
        return self.ev_max_charge_price_kr_per_kwh

    def get_fuse_capacity_w(self) -> int:
        return self.fuse_capacity_w

    def has_ev_charging(self) -> bool:
        """Check if EV charging is configured."""
        return (
            self.ev_max_capacity_wh is not None
            and self.ev_max_charge_speed_w is not None
        )

    @staticmethod
    def default_config() -> BatteryConfig:
        """Load configuration from the config file."""
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "config", "battery_config.json"
        )

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_data: dict[str, Any] = json.load(f)

            return BatteryConfig(
                grid_area=config_data["grid_area"],
                storage_size_wh=config_data["storage_size_wh"],
                initial_energy=config_data["initial_energy"],
                max_charge_speed_w=config_data["max_charge_speed_w"],
                max_discharge_speed_w=config_data["max_discharge_speed_w"],
                ev_max_capacity_wh=config_data.get("ev_max_capacity_wh"),
                ev_max_charge_speed_w=config_data.get("ev_max_charge_speed_w"),
                ev_max_charge_price_kr_per_kwh=config_data.get(
                    "ev_max_charge_price_kr_per_kwh", 2.0
                ),
                fuse_capacity_w=config_data.get("fuse_capacity_w", 11000),
            )
        except (FileNotFoundError, KeyError, json.JSONDecodeError) as e:
            print(f"Warning: Could not load battery config from {config_path}: {e}")
            print("Using fallback default values")
            return BatteryConfig(
                grid_area="SE3",
                storage_size_wh=44000,
                initial_energy=1000.0,
                max_charge_speed_w=8000,
                max_discharge_speed_w=9000,
            )
