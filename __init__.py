# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from .holidays import *

def register():
    Pool.register(
        HolidaysCalendar,
        HolidaysEvent,
        module='holidays_employee', type_='model')
