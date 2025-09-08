from datetime import date, timedelta
from calendar import monthrange
from dateutil.easter import easter
from dateutil.relativedelta import relativedelta

class RussianHolidays:
    @staticmethod
    def get_holidays(year):
        """Возвращает список праздничных дней в России для указанного года"""
        holidays = []
        
        # Новогодние каникулы (1-8 января)
        for day in range(1, 9):
            holidays.append(date(year, 1, day))
        
        # Рождество (7 января)
        holidays.append(date(year, 1, 7))
        
        # День защитника Отечества (23 февраля)
        holidays.append(date(year, 2, 23))
        
        # Международный женский день (8 марта)
        holidays.append(date(year, 3, 8))
        
        # Праздник Весны и Труда (1 мая)
        holidays.append(date(year, 5, 1))
        
        # День Победы (9 мая)
        holidays.append(date(year, 5, 9))
        
        # День России (12 июня)
        holidays.append(date(year, 6, 12))
        
        # День народного единства (4 ноября)
        holidays.append(date(year, 11, 4))
        
        # Пасха (переходящий праздник)
        easter_date = easter(year)
        holidays.append(easter_date)
        
        return holidays
    
    @staticmethod
    def is_holiday(check_date):
        """Проверяет, является ли дата праздничным днем"""
        holidays = RussianHolidays.get_holidays(check_date.year)
        return check_date in holidays
    
    @staticmethod
    def is_weekend(check_date):
        """Проверяет, является ли дата выходным днем"""
        return check_date.weekday() in [5, 6]  # 5 = суббота, 6 = воскресенье
    
    @staticmethod
    def is_working_day(check_date):
        """Проверяет, является ли дата рабочим днем"""
        return not (RussianHolidays.is_weekend(check_date) or RussianHolidays.is_holiday(check_date))

def get_working_days(year, month):
    """Возвращает список рабочих дней для указанного месяца"""
    first_day = date(year, month, 1)
    last_day = date(year, month, 1) + relativedelta(months=1) - timedelta(days=1)
    
    working_days = []
    non_working_days = []
    
    current_date = first_day
    while current_date <= last_day:
        if RussianHolidays.is_working_day(current_date):
            working_days.append(current_date.day)
        else:
            non_working_days.append({
                'day': current_date.day,
                'is_weekend': RussianHolidays.is_weekend(current_date),
                'is_holiday': RussianHolidays.is_holiday(current_date)
            })
        current_date += timedelta(days=1)
    
    return working_days, non_working_days