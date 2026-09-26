# calendar Module Complexity

The `calendar` module lays out months and years as grids of weeks and formats them as plain text
or HTML. No grid is built ahead of time: every call works its answer out by date arithmetic, and
a month never spans more than six weeks, so the grid behind any call has a fixed ceiling of 42 day
cells for a month and twelve months for a year.

With default arguments every operation on this page is O(1). What a caller can grow is the text
layout: `w` is the character width a `TextCalendar` method is given (its `width`, `w` or `n`
argument), `l` is the lines per week, and `c` is the spaces between month columns. `m`, the months
per row, is taken as at most 12. Years, months and days are priced as machine-size integers, a
week as the seven days the grids produce, day and month names, CSS class names and the stylesheet
URL as fixed-size strings, and each `strftime()` or `setlocale()`
call as O(1).

## Complexity Reference

### Module functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `calendar.isleap(year)` | O(1) | O(1) | |
| `calendar.leapdays(y1, y2)` | O(1) | O(1) | Leap years in `[y1, y2)`, counted arithmetically without visiting the range |
| `calendar.weekday(year, month, day)` | O(1) | O(1) | 0 is Monday; a year outside 1-9999 is folded into the 400-year Gregorian cycle |
| `calendar.monthrange(year, month)` | O(1) | O(1) | The month's first weekday and its number of days |
| `calendar.monthcalendar(year, month)` | O(1) | O(1) | Four to six week rows of seven day numbers, 0 outside the month |
| `calendar.timegm(tuple)` | O(1) | O(1) | The inverse of `time.gmtime()` |
| `calendar.firstweekday()` | O(1) | O(1) | |
| `calendar.setfirstweekday(weekday)` | O(1) | O(1) | Sets the first weekday of the one calendar the module functions share, so it changes what `monthcalendar()`, `weekheader()`, `month()`, `calendar()`, `prmonth()` and `prcal()` produce; raises `IllegalWeekdayError` outside 0-6 |
| `calendar.weekheader(n)` | O(w) | O(w) | Seven weekday names, each `n` characters wide |
| `calendar.week(theweek, width)` | O(w) | O(w) | `TextCalendar.formatweek()` on the shared calendar |
| `calendar.prweek(theweek, width)` | O(w) | O(w) | Prints what `week()` returns, without a newline |
| `calendar.month(theyear, themonth, w=0, l=0)` | O(w + l) | O(w + l) | |
| `calendar.prmonth(theyear, themonth, w=0, l=0)` | O(w + l) | O(w + l) | Prints what `month()` returns |
| `calendar.calendar(year, w=2, l=1, c=6, m=3)` | O(w + c + l) | O(w + c + l) | The whole year as one string |
| `calendar.prcal(year, w=0, l=0, c=6, m=3)` | O(w + c + l) | O(w + c + l) | Prints what `calendar()` returns |

### Calendar

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `calendar.Calendar(firstweekday=0)` | O(1) | O(1) | |
| `Calendar.firstweekday`, `Calendar.getfirstweekday()`, `Calendar.setfirstweekday(firstweekday)` | O(1) | O(1) | Read modulo 7; unlike the module function, nothing is range-checked |
| `Calendar.iterweekdays()` | O(1) | O(1) | Seven weekday numbers, starting at `firstweekday` |
| `Calendar.itermonthdays(year, month)` | O(1) | O(1) | Lazy, over whole weeks: day numbers, 0 outside the month |
| `Calendar.itermonthdays2(year, month)` | O(1) | O(1) | `(day, weekday)` pairs |
| `Calendar.itermonthdays3(year, month)` | O(1) | O(1) | `(year, month, day)` tuples; days outside the month carry their own month |
| `Calendar.itermonthdays4(year, month)` | O(1) | O(1) | `(year, month, day, weekday)` tuples |
| `Calendar.itermonthdates(year, month)` | O(1) | O(1) | `datetime.date` objects, so it raises `ValueError` where the padding days leave years 1-9999; the `itermonthdays` variants do not |
| `Calendar.monthdayscalendar(year, month)` | O(1) | O(1) | Four to six lists of seven day numbers |
| `Calendar.monthdays2calendar(year, month)` | O(1) | O(1) | The same grid of `(day, weekday)` pairs |
| `Calendar.monthdatescalendar(year, month)` | O(1) | O(1) | The same grid of `datetime.date` objects |
| `Calendar.yeardayscalendar(year, width=3)` | O(1) | O(1) | All twelve month grids, built eagerly and grouped `width` months to a row |
| `Calendar.yeardays2calendar(year, width=3)` | O(1) | O(1) | The same, of `(day, weekday)` pairs |
| `Calendar.yeardatescalendar(year, width=3)` | O(1) | O(1) | The same, of `datetime.date` objects |

### TextCalendar

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `calendar.TextCalendar(firstweekday=0)` | O(1) | O(1) | Every `Calendar` method, plus the formatting below |
| `TextCalendar.formatday(day, weekday, width)` | O(w) | O(w) | One day, centered to at least `width` characters |
| `TextCalendar.formatweek(theweek, width)` | O(w) | O(w) | Seven days joined by spaces |
| `TextCalendar.formatweekday(day, width)` | O(w) | O(w) | The full name when `width` is at least 9, otherwise the abbreviation, cut to `width` |
| `TextCalendar.formatweekheader(width)` | O(w) | O(w) | |
| `TextCalendar.formatmonthname(theyear, themonth, width, withyear=True)` | O(w) | O(w) | The name, centered to at least `width` characters |
| `TextCalendar.formatmonth(theyear, themonth, w=0, l=0)` | O(w + l) | O(w + l) | `w` is raised to at least 2 and `l` to at least 1 |
| `TextCalendar.formatyear(theyear, w=2, l=1, c=6, m=3)` | O(w + c + l) | O(w + c + l) | Every month is formatted once whatever `m` is; `m` only changes the layout |
| `TextCalendar.prweek(theweek, width)` | O(w) | O(w) | Prints `formatweek()` without a newline |
| `TextCalendar.prmonth(theyear, themonth, w=0, l=0)` | O(w + l) | O(w + l) | Prints `formatmonth()` |
| `TextCalendar.pryear(theyear, w=0, l=0, c=6, m=3)` | O(w + c + l) | O(w + c + l) | Prints `formatyear()` |

### HTMLCalendar

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `calendar.HTMLCalendar(firstweekday=0)` | O(1) | O(1) | Every `Calendar` method, plus the formatting below |
| `HTMLCalendar.formatday(day, weekday)` | O(1) | O(1) | One `<td>` |
| `HTMLCalendar.formatweek(theweek)` | O(1) | O(1) | One `<tr>` of seven cells |
| `HTMLCalendar.formatweekday(day)` | O(1) | O(1) | One `<th>` with the abbreviated name |
| `HTMLCalendar.formatweekheader()` | O(1) | O(1) | |
| `HTMLCalendar.formatmonthname(theyear, themonth, withyear=True)` | O(1) | O(1) | |
| `HTMLCalendar.formatmonth(theyear, themonth, withyear=True)` | O(1) | O(1) | One `<table>` |
| `HTMLCalendar.formatyear(theyear, width=3)` | O(1) | O(1) | Twelve month tables, `width` to a row |
| `HTMLCalendar.formatyearpage(theyear, width=3, css='calendar.css', encoding=None)` | O(1) | O(1) | A complete page, returned as `bytes` in `encoding` |
| `HTMLCalendar.cssclasses`, `HTMLCalendar.cssclasses_weekday_head`, `HTMLCalendar.cssclass_noday`, `HTMLCalendar.cssclass_month_head`, `HTMLCalendar.cssclass_month`, `HTMLCalendar.cssclass_year_head`, `HTMLCalendar.cssclass_year` | O(1) | O(1) | Class attributes read as each element is written; override them on a subclass or an instance |

### LocaleTextCalendar and LocaleHTMLCalendar

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `calendar.LocaleTextCalendar(firstweekday=0, locale=None)` | O(1) | O(1) | With `locale=None`, the default locale is looked up once, here |
| `calendar.LocaleHTMLCalendar(firstweekday=0, locale=None)` | O(1) | O(1) | The same, over `HTMLCalendar` |
| `LocaleTextCalendar.formatweekday(day, width)`, `LocaleTextCalendar.formatmonthname(theyear, themonth, width, withyear=True)` | O(w) | O(w) | Switches the process-wide `LC_TIME` locale to `locale` and back for each name, so it is not thread-safe |
| `LocaleHTMLCalendar.formatweekday(day)`, `LocaleHTMLCalendar.formatmonthname(theyear, themonth, withyear=True)` | O(1) | O(1) | The same switch for each name; every other method is inherited with its bound |

### Names and constants

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `calendar.day_name`, `calendar.day_abbr` | O(1) | O(1) | Indexed 0-6 from Monday; each access formats the name afresh with `strftime()` in the current `LC_TIME` locale |
| `calendar.month_name`, `calendar.month_abbr` | O(1) | O(1) | Indexed 1-12, with `''` at 0; each name is formatted on access in the same way |
| `calendar.MONDAY`, `calendar.TUESDAY`, `calendar.WEDNESDAY`, `calendar.THURSDAY`, `calendar.FRIDAY`, `calendar.SATURDAY`, `calendar.SUNDAY` | O(1) | O(1) | 0 to 6; `Day` members from Python 3.12, plain integers before |
| `calendar.JANUARY`, `calendar.FEBRUARY`, `calendar.MARCH`, `calendar.APRIL`, `calendar.MAY`, `calendar.JUNE`, `calendar.JULY`, `calendar.AUGUST`, `calendar.SEPTEMBER`, `calendar.OCTOBER`, `calendar.NOVEMBER`, `calendar.DECEMBER` | O(1) | O(1) | 1 to 12; Python 3.12+ |
| `calendar.Day`, `calendar.Month` | O(1) | O(1) | `IntEnum`s behind those constants; `weekday()` returns a `Day`. Python 3.12+ |

### Exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `calendar.IllegalMonthError`, `IllegalMonthError.month` | O(1) | O(1) | A `ValueError` raised by `monthrange()` and the `Calendar` methods for a month outside 1-12; `month` holds the value |
| `calendar.IllegalWeekdayError`, `IllegalWeekdayError.weekday` | O(1) | O(1) | A `ValueError` raised by `setfirstweekday()` for a weekday outside 0-6; `weekday` holds the value |

## Dates and Leap Years

Each of these answers from arithmetic on its arguments, so none of them walks a range of days or
years. `leapdays()` in particular costs the same for a span of ten years or a billion.

```python
import calendar
import time

assert calendar.weekday(2024, 1, 15) == calendar.MONDAY  # O(1)
assert calendar.monthrange(2024, 2) == (calendar.THURSDAY, 29)  # O(1)
assert calendar.isleap(2024) and not calendar.isleap(1900)  # O(1)

# O(1) for any span - the range is never visited
assert calendar.leapdays(2000, 2025) == 7
assert calendar.leapdays(1, 1_000_000_001) == 242_500_000

# Years beyond datetime's 1-9999 fold into the 400-year cycle
assert calendar.weekday(12024, 1, 15) == calendar.weekday(2024, 1, 15)

# timegm() is the inverse of time.gmtime()
stamp = 1_700_000_000
assert calendar.timegm(time.gmtime(stamp)) == stamp  # O(1)
```

## Month and Year Grids

A month grid is four to six weeks of seven days, and a year grid is twelve of those. Building the
lists and iterating lazily are therefore the same order of cost; pick whichever shape the code
wants. The iterators all pad to whole weeks, and differ only in what they yield for each day.

```python
import calendar
import datetime

cal = calendar.Calendar()  # O(1) - Monday first

weeks = cal.monthdayscalendar(2024, 2)  # O(1) - at most six rows of seven
assert weeks[0] == [0, 0, 0, 1, 2, 3, 4]
assert all(len(week) == 7 for week in weeks) and 4 <= len(weeks) <= 6

days = list(cal.itermonthdays2(2024, 2))  # O(1) - (day, weekday) pairs
assert days[3] == (1, calendar.THURSDAY)
assert len(days) == 7 * len(weeks)

# itermonthdays3 names the neighbouring month for padding days
assert next(cal.itermonthdays3(2024, 2)) == (2024, 1, 29)
assert next(cal.itermonthdates(2024, 2)) == datetime.date(2024, 1, 29)

year = cal.yeardayscalendar(2024, width=4)  # O(1) - all twelve months, four to a row
assert [len(row) for row in year] == [4, 4, 4]
```

### Beyond datetime's Range

`itermonthdates()` builds `datetime.date` objects, so a month whose padding days fall outside
years 1-9999 raises. The `itermonthdays` variants yield plain numbers and carry on.

```python
import calendar

cal = calendar.Calendar()

try:
    list(cal.itermonthdates(9999, 12))
except ValueError as error:
    assert '10000' in str(error)
else:
    raise AssertionError('a date in year 10000 was built')

assert list(cal.itermonthdays3(9999, 12))[-1] == (10000, 1, 2)  # O(1)
```

## The First Weekday

A `Calendar` instance keeps its own first weekday. The module functions share a single calendar,
so `setfirstweekday()` changes the month and year layouts they return, for the whole process.

```python
import calendar

sunday_first = calendar.Calendar(firstweekday=calendar.SUNDAY)  # O(1)
assert list(sunday_first.iterweekdays())[:2] == [6, 0]
assert sunday_first.monthdayscalendar(2024, 9)[0][0] == 1  # 1 September 2024 was a Sunday

# The module-level setting is global state: restore it afterwards
previous = calendar.firstweekday()
calendar.setfirstweekday(calendar.SUNDAY)  # O(1)
try:
    assert calendar.monthcalendar(2024, 9)[0][0] == 1
    assert calendar.weekheader(2).startswith('Su')
finally:
    calendar.setfirstweekday(previous)

try:
    calendar.setfirstweekday(7)
except calendar.IllegalWeekdayError as error:
    assert error.weekday == 7
else:
    raise AssertionError('a weekday of 7 was accepted')
```

## Formatting Text Calendars

A text calendar has a bounded number of rows, so its size follows the widths it is asked for: `w`
for each day column, `l` newlines after each row, and in a year, `c` spaces between months.

```python
import calendar

text = calendar.TextCalendar()

month = text.formatmonth(2024, 2)  # O(w + l)
assert month.splitlines()[0].strip() == 'February 2024'
assert month.splitlines()[1] == 'Mo Tu We Th Fr Sa Su'

# Ten times the column width is about ten times the text
narrow = text.formatmonth(2024, 2, w=10)
wide = text.formatmonth(2024, 2, w=100)
assert len(wide) > 8 * len(narrow)

year = calendar.calendar(2024)  # O(w + c + l)
assert year.lstrip().startswith('2024')
assert calendar.month(2024, 2) == month  # the module function is the shared TextCalendar
```

## HTML Calendars

`HTMLCalendar` writes a fixed set of tables, so every method is O(1). The CSS class names are
class attributes, read as each element is written, and `formatyearpage()` returns encoded bytes.

```python
import calendar

class Styled(calendar.HTMLCalendar):
    cssclass_month = 'month compact'
    cssclass_noday = 'empty'

html = Styled().formatmonth(2024, 2)  # O(1)
assert html.startswith('<table border="0" cellpadding="0" cellspacing="0" class="month compact">')
assert '<td class="empty">&nbsp;</td>' in html
assert '<td class="thu">1</td>' in html

page = calendar.HTMLCalendar().formatyearpage(2024, css=None, encoding='ascii')  # O(1)
assert isinstance(page, bytes)
assert b'<title>Calendar for 2024</title>' in page
```

## Localized Names

`day_name`, `day_abbr`, `month_name` and `month_abbr` store no names. Each name is
formatted by `strftime()` when it is looked up, in the current `LC_TIME` locale, which is what lets them follow a locale change;
a loop that looks names up per item can copy them into a list once.

`LocaleTextCalendar` and `LocaleHTMLCalendar` go further and switch the process-wide `LC_TIME`
locale for every name they format, then switch it back. That is a per-name cost on top of the
formatting, and it makes them unsafe to use from more than one thread.

```python
import calendar

assert calendar.day_name[0] == 'Monday'  # O(1) - formatted on this access
assert calendar.month_abbr[12] == 'Dec'
assert calendar.month_name[0] == ''
assert len(calendar.month_name) == 13

names = list(calendar.day_name)  # O(1) - seven strftime() calls, once
assert names[calendar.FRIDAY] == 'Friday'

# 'C' is available everywhere; a real deployment would pass e.g. 'de_DE.UTF-8'
local = calendar.LocaleTextCalendar(locale='C')  # O(1)
assert local.formatmonthname(2024, 2, 20).strip() == 'February 2024'  # switches LC_TIME and back
```

## Invalid Months

A month outside 1-12 raises `IllegalMonthError` from `monthrange()` and every `Calendar` method
built on it. It is a `ValueError`, so existing handlers catch it.

```python
import calendar

try:
    calendar.monthrange(2024, 13)
except calendar.IllegalMonthError as error:
    assert error.month == 13
    assert isinstance(error, ValueError)
else:
    raise AssertionError('month 13 was accepted')

try:
    calendar.Calendar().monthdayscalendar(2024, 0)
except ValueError as error:
    assert 'bad month number 0' in str(error)
else:
    raise AssertionError('month 0 was accepted')
```

## Common Patterns

### The Nth Weekday of a Month

The grid already pairs every day with its weekday, working out one weekday for the whole month, so
finding the fourth Thursday is a scan of at most 42 cells, not a `weekday()` call per day.

```python
import calendar

def nth_weekday(year, month, weekday, n):
    days = [day for day, wd in calendar.Calendar().itermonthdays2(year, month)
            if day and wd == weekday]  # O(1) - at most 42 cells
    return days[n - 1]

assert nth_weekday(2024, 11, calendar.THURSDAY, 4) == 28  # US Thanksgiving 2024
assert nth_weekday(2024, 5, calendar.MONDAY, 1) == 6
```

### Counting Working Days

```python
import calendar

def workdays(year, month):
    return sum(1 for day, wd in calendar.Calendar().itermonthdays2(year, month)
               if day and wd < calendar.SATURDAY)  # O(1)

assert workdays(2024, 2) == 21
assert workdays(2024, 9) == 21
```

### Leap Years Over a Span

```python
import calendar

span = range(1900, 2101)

by_loop = sum(calendar.isleap(year) for year in span)  # O(len(span))
by_formula = calendar.leapdays(span.start, span.stop)  # O(1)

assert by_loop == by_formula == 49
```

## Performance Best Practices

✅ **Do**:

- Use `leapdays()` for a span of years: it is O(1), where summing `isleap()` is linear in the
  number of years
- Take each day's weekday from `itermonthdays2()` or `monthdays2calendar()`: they work out one
  weekday for the month, where calling `weekday()` per day works out one per day
- Give a `Calendar` instance its own `firstweekday` rather than calling `setfirstweekday()`, which
  changes the module functions' layouts for the whole process
- Copy `list(calendar.day_name)` once for a loop that looks names up per item: each name lookup runs
  `strftime()`

❌ **Avoid**:

- Reaching for the lazy iterators to save memory: a month is at most 42 cells, so the lists cost
  the same order
- `itermonthdates()` for months at the edges of years 1-9999: it can raise when padding dates leave
  that range, where `itermonthdays3()` does not
- `LocaleTextCalendar` and `LocaleHTMLCalendar` from several threads: they switch the process-wide
  `LC_TIME` locale for each name

## Version Notes

- **Python 3.12+**: Added the `Day` and `Month` enums and the `JANUARY` to `DECEMBER` constants;
  `MONDAY` to `SUNDAY` became `Day` members, `weekday()` returns one, and `calendar.January` and
  `calendar.February` are deprecated

## Related Modules

- **[datetime](datetime.md)** - date arithmetic and the `date` objects `itermonthdates()` yields
- **[time](time.md)** - `time.gmtime()`, the inverse of `calendar.timegm()`
- **[locale](locale.md)** - the `LC_TIME` setting that names follow
