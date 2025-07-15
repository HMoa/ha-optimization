from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Activity(Enum):
    CHARGE = "charge"
    CHARGE_SOLAR_SURPLUS = "charge_solar_surplus"
    CHARGE_LIMIT = "charge_limit"
    DISCHARGE = "discharge"
    DISCHARGE_FOR_HOME = "discharge_for_home"
    DISCHARGE_LIMIT = "discharge_limit"
    SELF_CONSUMPTION = "self_consumption"
    IDLE = "idle"


@dataclass
class TimeslotItem:

    start_time: datetime
    prices: float
    battery_flow_wh: float
    battery_expected_soc_wh: float
    battery_expected_soc_percent: float
    house_consumption_wh: float
    activity: Activity
    grid_flow_wh: float  # Positive for import, negative for export
    amount: float | None = None

    def __post_init__(self) -> None:
        """Round all float values to 2 decimal places after initialization."""
        self.prices = round(self.prices, 2)
        self.battery_flow_wh = round(self.battery_flow_wh, 2)
        self.battery_expected_soc_wh = round(self.battery_expected_soc_wh, 2)
        self.battery_expected_soc_percent = round(self.battery_expected_soc_percent, 2)
        self.house_consumption_wh = round(self.house_consumption_wh, 2)
        self.grid_flow_wh = round(self.grid_flow_wh, 2)
        if self.amount is not None:
            self.amount = round(self.amount, 2)


nätnytta = 0.08
skatteavdrag = 0.6

delivery_fee = 0.4  # 0.06-0.6 kr
energi_skatt = 0.55


class Elpris:
    def __init__(self, spot_price: float) -> None:
        self.buy_price: float = spot_price + delivery_fee + energi_skatt
        self.sell_price: float = spot_price + nätnytta + skatteavdrag
        self.spot_price: float = spot_price

    def get_sell_price(self) -> float:
        return self.sell_price

    def get_buy_price(self) -> float:
        return self.buy_price

    def get_spot_price(self) -> float:
        return self.spot_price
