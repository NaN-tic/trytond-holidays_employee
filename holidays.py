#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from trytond.model import fields
from trytond.pyson import Eval, Bool
from trytond.model import ModelView
from trytond.modules.calendar.calendar_ import Calendar, Event
from trytond.transaction import Transaction
from datetime import timedelta, datetime, time
import pytz


__all__ = ['HolidaysCalendar', 'HolidaysEvent']


class HolidaysCalendar(Calendar):
    'Holidays Calendar'
    __name__ = 'holidays_employee.calendar'
    _table = 'holidays_employee_calendar'

    events = fields.One2Many('holidays_employee.event', 'calendar',
        'Holiday Event')
    general_holidays = fields.Boolean('General Holidays')
    employee = fields.Many2One('company.employee', 'Employee', states={
            'invisible': Bool(Eval('general_holidays')),
            'required': ~Bool(Eval('general_holidays')),
            }, depends=['general_holidays'])
    total_days = fields.Float('Total Holidays', digits=(16, 2))
    remaining_days = fields.Function(
        fields.Float('Remaining Days', digits=(16, 2)),
        'get_remainig_days')
    elective_days = fields.Float('Total Elective days', digits=(16, 2))
    remaining_elective_days = fields.Function(
        fields.Float('Remaining Elective Days', digits=(16, 2)),
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
    def default_general_holidays():
        return False

    @staticmethod
    def default_total_days():
        return 23

    @staticmethod
    def default_elective_days():
        return 2

    @staticmethod
    def default_state():
        return 'opened'

    @classmethod
    def get_remainig_days(cls, calendars, names):
        res = {}
        for fname in names:
            res[fname] = {}

        for calendar in calendars:
            days = 0
            edays = 0
            for event in calendar.events:
                if not event.elective:
                    days += event.days
                else:
                    edays += event.edays
            res['remaining_days'][calendar.id] = calendar.total_days - days
            res['remaining_elective_days'][calendar.id] = calendar.elective_days - edays
        return res

    def get_rec_name(self, name):
        if not self.general_holidays:
            return self.name + ' - ' + self.employee.party.name
        User = Pool().get('res.user')
        user = User(Transaction().user)
        company_name = (user and user.company and user.company.party and
            user.company.party.name or "")
        if company_name:
            return self.name + ' - ' + company_name
        return self.name

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
    start_date = fields.Function(fields.Date('Start Date',required=True),
        'get_start_date', setter='set_dates', searcher='search_date')
    end_date = fields.Function(fields.Date('End Date'),
        'get_end_date', setter='set_dates', searcher='search_date')
    days = fields.Function(fields.Float('Number of Days', digits=(16, 2)),
        'on_change_with_days')
    elective = fields.Boolean('Elective Day')
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
                'invalidelective__days': ('You have selected to much elective '
                    'days. You have only %s days free.'),
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

    @staticmethod
    def default_elective():
        return False

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
            event.check_elective_days()
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

    def check_elective_days(self):
        if self.calendar.elective_days < self.calendar.remaining_elective_days + self.days:
            self.raise_user_error('invalid_elective_days',
                (self.calendar.remaining_elective_days))

    def get_start_date(self, name=None):
        return self.dtstart.date()

    def get_end_date(self, name=None):
        return self.dtend.date()

    @classmethod
    def set_dates(cls, events, name, value):
        pass

    @classmethod
    def search_dates(cls, name, clause):
        new_name = 'dtend' if name == 'end_date' else 'dtstart'
        _, operator, value = clause[:2]
        value = datetime.combine(value, time(23, 59, tzinfo=pytz.utc))
        return [(new_name, operator, value)]

    def _on_change_date(self, change):
        result = {}
        if self.dtstart_type == 'morning' and self.start_date or (
            self.dtstart_type in ('afternoon', 'all_day')
            and self.start_date and self.end_date
            and self.start_date == self.end_date):
            result['dtend_type'] = self.dtstart_type
            result['dtstart'] =datetime.combine(self.start_date, time(0, 0,
                    tzinfo=pytz.utc))
            result['dtend'] = datetime.combine(self.start_date, time(11, 59,
                    tzinfo=pytz.utc))

            result['end_date'] = self.start_date
        elif self.dtstart_type == 'morning':
            result['dtend_type'] = self.dtstart_type
        if change in ('start_date', 'dtstart_type') and self.dtstart:
            if self.dtstart_type == 'all_day':
                result['dtstart'] = datetime.combine(self.start_date, time(0,
                        0, tzinfo=pytz.utc))
            elif self.dtstart_type == 'afternoon':
                result['dtstart'] = datetime.combine(self.start_date, time(12,
                        0, tzinfo=pytz.utc))
        elif change in ('end_date', 'dtend_type') and self.end_date:
            if self.dtend_type == 'morning':
                result['dtend'] = datetime.combine(self.end_date, time(11,59,
                        tzinfo=pytz.utc))
            else:
                result['dtend'] = datetime.combine(self.end_date, time(23, 59,
                        tzinfo=pytz.utc))
        return result

    @fields.depends('start_date', 'end_date', 'dtstart_type', 'dtend_type',
        'dtstart', 'dtend')
    def on_change_start_date(self, name=None):
        return self._on_change_date('start_date')

    @fields.depends('start_date', 'end_date', 'dtstart_type', 'dtend_type',
        'dtstart', 'dtend')
    def on_change_end_date(self):
        return self._on_change_date('end_date')

    @fields.depends('start_date', 'end_date', 'dtstart_type', 'dtend_type',
        'dtstart', 'dtend')
    def on_change_dtstart_type(self, name=None):
        return self._on_change_date('dtstart_type')

    @fields.depends('start_date', 'end_date', 'dtstart_type', 'dtend_type',
        'dtstart', 'dtend')
    def on_change_dtend_type(self, name=None):
        return self._on_change_date('dtend_type')

    @fields.depends('start_date', 'end_date', 'dtstart_type', 'dtend_type')
    def on_change_with_days(self, name=None):
        if self.dtstart_type == 'morning':
            return 0.5
        number = 0
        if self.start_date and self.end_date:
            start_date = self.start_date - timedelta(days=1)
            if self.dtstart_type == 'afternoon':
                number -= 0.5
            if self.dtend_type == 'morning':
                number -= 0.5
            return (self.end_date - start_date).days + number
        return number
