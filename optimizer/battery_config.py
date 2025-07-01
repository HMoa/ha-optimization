from __future__ import annotations


class BatteryConfig:
    def __init__(
        self,
        grid_area: str,
        storage_size_wh: int,
        initial_energy: float,
        max_charge_speed_w: int,
        max_discharge_speed_w: int,
    ) -> None:
        self.grid_area: str = grid_area
        self.storage_size_wh: int = storage_size_wh
        self.initial_energy: float = initial_energy
        self.max_charge_speed_w: int = max_charge_speed_w
        self.max_discharge_speed_w: int = max_discharge_speed_w

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

    @staticmethod
    def default_config() -> BatteryConfig:
        return BatteryConfig(
            grid_area="SE3",
            storage_size_wh=44000,
            initial_energy=1000.0,
            max_charge_speed_w=8000,
            max_discharge_speed_w=9000,
        )
