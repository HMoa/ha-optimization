from datetime import datetime


def get_consumption(start_date: datetime, end_date: datetime):
    from datetime import timedelta
    from random import randint

    # Snap start_date to the closest 5-minute interval
    start_date = start_date - timedelta(
        minutes=start_date.minute % 5,
        seconds=start_date.second,
        microseconds=start_date.microsecond,
    )

    consumption_data = {}
    current_time = start_date

    while current_time <= end_date:
        consumption_data[current_time] = randint(0, 50)
        current_time += timedelta(minutes=5)
    return consumption_data
