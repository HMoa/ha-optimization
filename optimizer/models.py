from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


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
    amount: Optional[float] = None


nätnytta = 0.08
skatteavdrag = 0.6

delivery_fee = 0.4  # 0.06-0.6 kr
energi_skatt = 0.55


class Elpris:
    def __init__(self, spot_price):
        self.buy_price = spot_price + delivery_fee + energi_skatt
        self.sell_price = spot_price + nätnytta + skatteavdrag
        self.spot_price = spot_price

    def get_sell_price(self):
        return self.sell_price

    def get_buy_price(self):
        return self.buy_price

    def get_spot_price(self):
        return self.spot_price
