class BatteryConfig:
    def __init__(
        self,
        grid_area: str,
        storage_size_wh: int,
        initial_energy: int,
        max_charge_speed_w: int,
        max_discharge_speed_w: int,
    ):
        self.grid_area = grid_area
        self.storage_size_wh = storage_size_wh
        self.initial_energy = initial_energy
        self.max_charge_speed_w = max_charge_speed_w
        self.max_discharge_speed_w = max_discharge_speed_w

    def get_grid_area(self):
        return self.grid_area

    def get_storage_size_wh(self):
        return self.storage_size_wh

    def get_initial_energy(self):
        return self.initial_energy

    def get_max_charge_speed_w(self):
        return self.max_charge_speed_w

    def get_max_discharge_speed_w(self):
        return self.max_discharge_speed_w

    @staticmethod
    def default_config():
        return BatteryConfig(
            grid_area="SE3",
            storage_size_wh=44000,
            initial_energy=5000,
            max_charge_speed_w=5000,
            max_discharge_speed_w=5000,
        )
