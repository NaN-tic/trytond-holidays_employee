#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pyson import Eval
from trytond.model import ModelView
from trytond.modules.calendar.calendar_ import Calendar, Event


__all__ = ['HolidaysCalendar', 'HolidaysEvent']


class HolidaysCalendar(Calendar):
    'Holidays Calendar'
    __name__ = 'holidays_employee.calendar'
    _table = 'holidays_employee_calendar'

    events = fields.One2Many('holidays_employee.event', 'calendar',
        'Holiday Event')
    employee = fields.Many2One('company.employee', 'Employee', required=True)
    total_days = fields.Float('Total Holidays', digits=(16, 2))
    remaining_days = fields.Function(
        fields.Float('Remaining Days', digits=(16, 2)),
        'get_remainig_days')
    state = fields.Selection([
            ('opened', 'Opened'),
            ('done', 'Done'),
            ], 'State', readonly=True)

    @classmethod
    def __setup__(cls):
        super(HolidaysCalendar, cls).__setup__()
        cls._buttons.update({
                'open': {
                    'invisible': Eval('state') == 'opened',
                    },
                'done': {
                    'invisible': Eval('state') == 'done',
                    },
                })
        cls._sql_constraints = [
            ('name_employee_uniq', 'UNIQUE(name, employee)',
                'The realtion of the name and the employee of holidays must be unique.'),
            ]

    @staticmethod
    def default_holiday():
        return False

    @staticmethod
    def default_total_days():
        return 23

    @staticmethod
    def default_state():
        return 'opened'

    def get_remainig_days(self, name):
        days = 0
        for event in self.events:
            days += event.days
        return self.total_days - days

    def get_rec_name(self, name):
        return self.name + ' - ' + self.employee.party.name

    @classmethod
    @ModelView.button
    def open(cls, holidays_calendar):
        for holiday in holidays_calendar:
            holiday.state = 'opened'
            holiday.save()

    @classmethod
    @ModelView.button
    def done(cls, holidays_calendar):
        for holiday in holidays_calendar:
            holiday.state = 'done'
            holiday.save()

    #@classmethod
    #def delete(cls, events):
    #    return super(Event, cls).delete(events)


class HolidaysEvent(Event):
    'Holidays Event'
    __name__ = 'holidays_employee.event'
    _table = 'holidays_employee_event'

    calendar = fields.Many2One('holidays_employee.calendar', 'Calendar',
            required=True, select=True, ondelete="CASCADE")
    dtstart_type = fields.Selection([
        ('all_day', 'All Day'),
        ('morning', 'Morning'),
        ('afternoon', 'Afternoon'),
        ], 'Start Date Type', on_change=['dtstart', 'dtend', 'dtstart_type',
            'dtend_type'], required=True)
    dtend_type = fields.Selection([
        ('all_day', 'All Day'),
        ('morning', 'Morning'),
        ('afternoon', 'Afternoon'),
        ], 'End Date Type',  on_change=['dtstart', 'dtend', 'dtstart_type',
            'dtend_type'])
    days = fields.Function(fields.Float('Number of Days',
            digits=(16, 2), on_change_with=[
                'dtstart', 'dtend', 'dtstart_type', 'dtend_type']),
        'on_change_with_days')
    state = fields.Function(fields.Selection([
                ('opened', 'Opened'),
                ('done', 'Done'),
                ], 'State', select=True), 'get_state', searcher='search_state')

    @classmethod
    def __setup__(cls):
        super(Event, cls).__setup__()
        if cls.dtstart.on_change:
            cls.dtstart.on_change |= ['dtstart', 'dtend', 'dtstart_type',
                'dtend_type']
        else:
            cls.dtstart.on_change = ['dtstart', 'dtend', 'dtstart_type',
                'dtend_type']
        if cls.dtend.on_change:
            cls.dtend.on_change |= ['dtstart', 'dtend', 'dtstart_type',
                'dtend_type']
        else:
            cls.dtend.on_change = ['dtstart', 'dtend', 'dtstart_type',
                'dtend_type']

        cls._error_messages.update({
                'invalid_dates': ('The End Date (%s) is higher of the Start '
                    'Date (%s), and that it is not possible.'),
                'invalid_days': ('You have selected to much days. You have '
                    'only %s days free.'),
                })

    @staticmethod
    def default_dtstart_type():
        return 'all_day'

    @staticmethod
    def default_dtend_type():
        return 'all_day'

    @staticmethod
    def default_status():
        return 'tentative'

    @staticmethod
    def default_type():
        return 'all_day'

    @staticmethod
    def default_days():
        return 0

    def get_state(self, name=None):
        return self.calendar.state if self.calendar else 'opened'

    @classmethod
    def search_state(cls, name, clause):
        event = cls.search([], limit=1)
        if event:
            return [('calendar.state',) + tuple(clause[1:])]
        return []

    @classmethod
    def validate(cls, events):
        for event in events:
            event.check_dates()
            event.check_days()
        super(HolidaysEvent, cls).validate(events)

    def check_dates(self):
        if self.dtend:
            if self.dtstart > self.dtend:
                self.raise_user_error('invalid_dates', (self.dtend,
                        self.dtstart))

    def check_days(self):
        if self.calendar.total_days < self.calendar.remaining_days + self.days:
            self.raise_user_error('invalid_days',
                (self.calendar.remaining_days))

    def onchange_dates(self, change):
        result = {}
        if change in ('dtstart', 'dtstart_type') and self.dtstart:
            if self.dtstart_type == 'morning':
                result['dtstart'] = self.dtstart.replace(hour=0, minute=0,
                    second=0, microsecond=0)
                result['dtend_type'] = self.dtstart_type
                result['dtend'] = self.dtstart.replace(hour=11, minute=59,
                    second=59, microsecond=999999)
            else:
                result['dtend_type'] = self.dtstart_type
                result['dtend'] = self.dtstart.replace(hour=23, minute=59,
                    second=59, microsecond=999999)
                if self.dtstart_type == 'afternoon':
                    result['dtstart'] = self.dtstart.replace(hour=12, minute=0,
                        second=0, microsecond=0)
                else:
                    result['dtstart'] = self.dtstart.replace(hour=0, minute=0,
                        second=0, microsecond=0)
        elif change in ('dtend', 'dtend_type') and self.dtend:
            if self.dtend_type == 'morning':
                result['dtend'] = self.dtend.replace(hour=11, minute=59,
                    second=59, microsecond=999999)
            elif self.dtend_type == 'afternoon':
                result['dtend_type'] = self.dtstart_type
                result['dtend'] = self.dtstart.replace(hour=23, minute=59,
                    second=59, microsecond=999999)
            else:
                result['dtend'] = self.dtend.replace(hour=23, minute=59,
                    second=59, microsecond=999999)
        return result

    def on_change_dtstart(self):
        return self.onchange_dates('dtstart')

    def on_change_dtend(self):
        return self.onchange_dates('dtend')

    def on_change_dtstart_type(self):
        return self.onchange_dates('dtstart_type')

    def on_change_dtend_type(self):
        return self.onchange_dates('dtend_type')

    def on_change_with_days(self, name=None):
        number = 0
        if self.dtstart and self.dtend:
            days = (self.dtend - self.dtstart).total_seconds()/60/60/24
            number = float("%.2f" % days)
        return number
