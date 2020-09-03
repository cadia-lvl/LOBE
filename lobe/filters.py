from babel.dates import format_datetime


def format_date(value, format='medium'):
    if format == 'full':
        format = "EEEE, d. MMMM y 'at' HH:mm"
    elif format == 'medium':
        format = "EE dd.MM.y HH:mm"
    elif format == 'med-low':
        format = "dd.MM.y HH:mm"
    elif format == 'low':
        format = "dd.MM.y"
    elif format == 'hm':
        # hours and minutes
        format = "HH:mm"
    return format_datetime(value, format)
