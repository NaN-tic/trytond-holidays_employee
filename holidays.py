#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pyson import Eval
from trytond.model import ModelView
from trytond.modules.calendar.calendar_ import Calendar, Event
from datetime import timedelta, datetime, time


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
                'The realtion of the name and the employee of holidays must be'
                ' unique.'),
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
            ], 'Start Date Type', required=True)
    dtend_type = fields.Selection([
            ('all_day', 'All Day'),
            ('morning', 'Morning'),
            ('afternoon', 'Afternoon'),
            ], 'End Date Type')
    start_date = fields.Function(fields.Date('Start Date'),
        'get_start_date', setter='set_dates',
        searcher='search_date')
    end_date = fields.Function(fields.Date('End Date'),
        'get_end_date', setter='set_dates', searcher='search_date')
    days = fields.Function(fields.Float('Number of Days', digits=(16, 2)),
        'on_change_with_days')
    state = fields.Function(fields.Selection([
                ('opened', 'Opened'),
                ('done', 'Done'),
                ], 'State', select=True), 'get_state', searcher='search_state')

    @classmethod
    def __setup__(cls):
        super(Event, cls).__setup__()
        cls._error_messages.update({
                'invalid_dates': ('The End Date (%s) is higher of the Start '
                    'Date (%s), and that it is not possible.'),
                'invalid_days': ('You have selected to much days. You have '
                    'only %s days free.'),
                })

    @staticmethod
    def default_dtstart():
        return datetime.now()

    @staticmethod
    def default_dtend():
        return datetime.now()

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

    def get_start_date(self, name=None):
        return self.dtstart.date()

    def get_end_date(self, name=None):
        return self.dtend.date()

    @classmethod
    def set_dates(cls, events, name, value):
        fname = 'dtend' if name == 'end_date' else 'dtstart'
        cls.write(events, {fname: datetime.combine(value, time(0, 00))})

    @classmethod
    def write(cls, *args):
        actions = iter(args)
        to_write = []
        for events, vals in zip(actions, actions):
            for event in events:
                if vals.get('dtstart_type', event.dtstart_type) == 'morning':
                    dtstart = vals.get('dtstart', event.dtstart)
                    vals['dtstart'] = datetime.combine(dtstart, time(0, 0))
                    vals['dtend'] = datetime.combine(dtstart, time(11, 59))
                    vals['dtend_type'] = 'morning'
                    to_write.extend(([event], vals))
                    continue
                for fname in ('dtstart', 'dtend'):
                    value = vals.get(fname, getattr(event, fname))
                    ctime = time(23, 59)
                    if fname == 'dtstart':
                        if (vals.get('dstart_type', event.dtstart_type) ==
                                'afternoon'):
                            ctime == time(12, 00)
                        else:
                            ctime = time(0, 0)
                    elif vals.get('dtend_type', event.dtend_type) == 'morning':
                            ctime == time(11, 59)
                    vals[fname] = datetime.combine(value, ctime)
                to_write.extend(([event], vals))
        super(HolidaysEvent, cls).write(*to_write)

    @classmethod
    def search_dates(cls, name, clause):
        new_name = 'dtend' if name == 'end_date' else 'dtstart'
        _, operator, value = clause[:2]
        value = datetime.combine(value, time(23, 59))
        return [(new_name, operator, value)]

    @fields.depends('dtstart_type')
    def on_change_with_dtend_type(self):
        return self.dtstart_type

    @fields.depends('start_date', 'dtstart_type', 'end_date', 'dtend_type')
    def on_change_with_days(self, name=None):
        if self.dtstart_type == 'morning':
            return 0.5
        number = 0
        if self.dtstart_type == 'afternoon':
            number += 0.5
        if self.dtend_type == 'morning':
            number -= 0.5
        if self.start_date and self.end_date:
            start_date = self.start_date
            if self.dtstart_type == 'all_day':
                start_date = self.start_date - timedelta(days=1)
            return (self.end_date - start_date).days + number
        return number
