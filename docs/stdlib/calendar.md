# Calendar Module

The `calendar` module provides calendar-related functions and classes for working with calendars.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `calendar()` | O(n) | O(n) | n = days in period |
| `monthcalendar()` | O(1) | O(1) | Returns fixed structure |
| `weekday()` | O(1) | O(1) | Day of week |
| `monthrange()` | O(1) | O(1) | Month info |
| `itermonthdays()` | O(n) | O(1) | n = days in month |
| `isleap()` | O(1) | O(1) | Check leap year |

## Common Operations

### Getting Calendar Information

```python
import calendar

# O(1) - get day of week (0=Monday, 6=Sunday)
day_of_week = calendar.weekday(2024, 1, 15)  # 0 = Monday

# O(1) - get first weekday and number of days in month
first_day, num_days = calendar.monthrange(2024, 1)
# Returns: (0, 31) - Jan 2024 starts on Monday, has 31 days

# O(1) - check if leap year
is_leap = calendar.isleap(2024)  # True
```

### Generating Calendar Strings

```python
import calendar

# O(n) where n = days in period
# Print full year calendar
year_str = calendar.calendar(2024)

# O(n) where n = days in month
# Print month calendar
month_str = calendar.month(2024, 1)
# Returns formatted month string

# O(n) where n = rows in calendar
# Print month as string
month_lines = calendar.month(2024, 1).split('\n')
```

### Working with Calendar Objects

```python
import calendar

# O(1) - create calendar object
cal = calendar.Calendar()

# O(n) where n = days in month
# Get all weeks in month
weeks = cal.monthdayscalendar(2024, 1)
# Returns: [[1, 2, 3, ...], [8, 9, 10, ...], ...]

# O(n) - iterate days with weekdays
for day, weekday_num in cal.itermonthdays2(2024, 1):
    # day: 1-31 (or 0 for days from other months)
    # weekday_num: 0-6
    print(f"Day {day}: {calendar.day_name[weekday_num]}")

# O(n) - iterate only days in month
for day in cal.itermonthdays(2024, 1):
    if day == 0:  # From other month
        continue
    print(day)
```

### Working with Specific Calendar Systems

```python
import calendar

# O(n) - Sunday-based calendar
cal_sunday = calendar.Calendar(firstweekday=6)
weeks = cal_sunday.monthdayscalendar(2024, 1)

# O(n) - Monday-based calendar (default)
cal_monday = calendar.Calendar(firstweekday=0)
weeks = cal_monday.monthdayscalendar(2024, 1)

# O(1) - get day name
day_name = calendar.day_name[0]  # 'Monday'
month_name = calendar.month_name[1]  # 'January'
```

## Common Use Cases

### Finding Specific Days in a Month

```python
import calendar

def find_day_in_month(year, month, target_day):
    """Find all occurrences of a day in month - O(n)"""
    # O(n) where n = days in month
    cal = calendar.Calendar()
    occurrences = []
    
    for week in cal.monthdayscalendar(year, month):
        # target_day: 0=Monday, 6=Sunday
        if week[target_day] != 0:  # O(1) index access
            occurrences.append(week[target_day])
    
    return occurrences

# O(n) - find all Fridays (4) in January 2024
fridays = find_day_in_month(2024, 1, 4)
print(fridays)  # [5, 12, 19, 26]
```

### Building a Weekly Schedule

```python
import calendar

def get_week_schedule(year, month, week_num):
    """Get a specific week's days - O(1)"""
    cal = calendar.Calendar()
    
    # O(n) to get all weeks where n = days in month
    weeks = cal.monthdayscalendar(year, month)
    
    # O(1) to access specific week
    if week_num < len(weeks):
        week = weeks[week_num]
        
        # O(7) = O(1) to build schedule
        schedule = {}
        for i, day in enumerate(week):
            if day != 0:  # Valid day
                day_name = calendar.day_name[i]
                schedule[day_name] = day
        
        return schedule
    return {}

# Usage - O(n)
schedule = get_week_schedule(2024, 1, 0)  # First week
print(schedule)
```

### Calendar Comparison

```python
import calendar

def days_until_target(year, month, day, target_weekday):
    """Calculate days until next occurrence - O(1)"""
    # O(1) - get weekday of given date
    current_weekday = calendar.weekday(year, month, day)
    
    # O(1) - calculate difference
    if target_weekday > current_weekday:
        days_diff = target_weekday - current_weekday
    else:
        days_diff = (7 - current_weekday) + target_weekday
    
    return days_diff

# O(1) - days until next Friday (4) from Jan 1, 2024 (Monday=0)
days = days_until_target(2024, 1, 1, 4)  # Friday
print(days)  # 4 days
```

### Work Day Calculation

```python
import calendar

def count_workdays(year, month):
    """Count weekdays (Mon-Fri) in month - O(n)"""
    cal = calendar.Calendar()
    workdays = 0
    
    # O(n) where n = days in month
    for day in cal.itermonthdays(year, month):
        if day == 0:  # Skip days from other months
            continue
        
        # O(1) - get weekday (0-6, 0=Monday)
        weekday = calendar.weekday(year, month, day)
        
        # O(1) - check if weekday (0-4 = Mon-Fri)
        if weekday < 5:  # Monday to Friday
            workdays += 1
    
    return workdays

# Usage - O(n)
work_days = count_workdays(2024, 1)
print(f"Workdays in January 2024: {work_days}")
```

## Performance Tips

### Cache Leap Year Checks

```python
import calendar

class DateHelper:
    """Cache leap year checks - O(1) after first call"""
    
    def __init__(self):
        self._leap_cache = {}
    
    def is_leap(self, year):
        """O(1) cached lookup"""
        if year not in self._leap_cache:
            # O(1) first time
            self._leap_cache[year] = calendar.isleap(year)
        return self._leap_cache[year]

# Usage
helper = DateHelper()
is_leap = helper.is_leap(2024)  # O(1) after cache
```

### Reuse Calendar Objects

```python
import calendar

# Bad: Create new calendar each time - O(n) per call
def get_weeks_bad(year, month):
    return calendar.Calendar().monthdayscalendar(year, month)

# Good: Reuse calendar object - O(1) object creation
cal = calendar.Calendar()

def get_weeks_good(year, month):
    return cal.monthdayscalendar(year, month)  # O(n) only for data
```

### Use itermonthdays for Memory Efficiency

```python
import calendar

# Bad: Load all weeks into memory - O(n) space
weeks = calendar.Calendar().monthdayscalendar(2024, 1)
for week in weeks:
    for day in week:
        process(day)

# Good: Iterate directly - O(1) space
for day in calendar.Calendar().itermonthdays(2024, 1):
    if day != 0:
        process(day)  # O(1) per item
```

## Version Notes

- **Python 2.6+**: Core functionality available
- **Python 3.x**: All features available
- **Python 3.12+**: Performance improvements

## Related Documentation

- [Datetime Module](datetime.md) - Date/time operations
- [Time Module](time.md) - Time operations
