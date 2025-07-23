from __future__ import annotations

import os
from datetime import datetime, timedelta

import joblib
import numpy as np
import pandas as pd


def get_production(start_date: datetime, end_date: datetime) -> dict[datetime, float]:
    # Snap start_date to the closest 5-minute interval
    start_date = start_date - timedelta(
        minutes=start_date.minute % 5,
        seconds=start_date.second,
        microseconds=start_date.microsecond,
    )

    production_data: dict[datetime, float] = {}
    current_time = start_date

    model_path = os.path.join(
        os.path.dirname(__file__), "../models/pv_production.joblib"
    )
    model = joblib.load(model_path)

    # Generate time slots between start_date and end_date (inclusive) at 5-minute intervals
    time_slots = []
    t = current_time
    while t <= end_date:
        time_slots.append(t)
        t += timedelta(minutes=5)

    # Prepare features for prediction
    # Calculate cyclical features for each time slot
    minutes_of_day = [dt.hour * 60 + dt.minute for dt in time_slots]
    day_of_year = [dt.timetuple().tm_yday for dt in time_slots]
    sin_day = [np.sin((m / 1440) * 2 * 3.141592653589793) for m in minutes_of_day]
    cos_day = [np.cos((m / 1440) * 2 * 3.141592653589793) for m in minutes_of_day]
    sin_year = [np.sin((d / 365) * 2 * 3.141592653589793) for d in day_of_year]
    cos_year = [np.cos((d / 365) * 2 * 3.141592653589793) for d in day_of_year]

    df = pd.DataFrame(
        {
            "sin_day": sin_day,
            "cos_day": cos_day,
            "sin_year": sin_year,
            "cos_year": cos_year,
        }
    )

    preds = model.predict(df)
    for dt, pred in zip(time_slots, preds):
        production_data[dt] = max(0, float(pred))

    return production_data


if __name__ == "__main__":
    response = get_production(
        datetime(2025, 6, 1, 11, 0, 0), datetime(2025, 6, 1, 11, 10, 0)
    )
    print(response)
