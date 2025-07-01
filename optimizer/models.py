from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Activity(Enum):
    CHARGE = "charge"
    DISCHARGE = "discharge"
    SELF_CONSUMPTION = "self_consumption"
    IDLE = "idle"


@dataclass
class TimeslotItem:

    start_time: datetime
    prices: float
    battery_flow: float
    battery_expected_soc: float
    house_consumption: float
    activity: Activity
    grid_flow: float  # Positive for import, negative for export
    amount: float | None = None


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
