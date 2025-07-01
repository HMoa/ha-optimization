from __future__ import annotations

from models import Activity, TimeslotItem


def set_battery_in_state(timeslot_item: TimeslotItem) -> None:
    if timeslot_item.activity == Activity.CHARGE:
        print("Charging")
    elif timeslot_item.activity == Activity.DISCHARGE:
        print("Discharging")
    elif timeslot_item.activity == Activity.IDLE:
        print("Idle")
    elif timeslot_item.activity == Activity.SELF_CONSUMPTION:
        print("Self consumption")
