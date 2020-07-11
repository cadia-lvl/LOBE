from datetime import datetime,timedelta
import time

def last_day(day_name, d=datetime.now()):
    days_of_week = ['sunday','monday','tuesday','wednesday',
                        'thursday','friday','saturday']
    target_day = days_of_week.index(day_name.lower())
    delta_day = target_day - d.isoweekday()
    if delta_day >= 0: delta_day -= 7 # go back 7 days
    return d + timedelta(days=delta_day)