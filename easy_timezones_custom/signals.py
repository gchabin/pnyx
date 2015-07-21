__author__ = 'guillaumechabin'
'''
from Easy_time_timezone
https://github.com/Miserlou/django-easy-timezones/blob/master/easy_timezones/signals.py
The update allows to set the timezone to UTC in the Admin interface
'''

# Django
import django.dispatch
detected_timezone = django.dispatch.Signal(providing_args=["instance", "timezone"])