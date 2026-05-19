import datetime
import calendar
import os.path
import pickle
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
WORK_START_HOUR, WORK_END_HOUR = 10, 22
MIN_FREE_INTERVAL = 60  # минут
SHOW_DATES = False

# Режим отображения расписания:
# 'next' - только следующая неделя
# 'two_weeks' - общие окна на двух неделях (текущая и следующая)
# False - не считать окна
SCHEDULE_MODE = False

# Подсчет месячной зп
MUNTH_SUM = True


def get_credentials():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)

    path = 'credentials.json'
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(path):
                raise FileNotFoundError("Файл credentials.json не найден")
            flow = InstalledAppFlow.from_client_secrets_file(path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    return creds

def parse_time(dt_str: str, tz_info) -> datetime.datetime:
    "Парсит время из строки Google Calendar"
    if dt_str.endswith('Z'):
        dt_str = dt_str[:-1] + '+00:00'
    dt = datetime.datetime.fromisoformat(dt_str)
    return dt.astimezone(tz_info) if dt.tzinfo else dt.replace(tzinfo=datetime.timezone.utc).astimezone(tz_info)

def get_week_range(week_offset: int = 0) -> tuple[datetime.datetime, datetime.datetime]:
    "Возвращает начало и конец недели со смещением"
    now = datetime.datetime.now().astimezone()
    start = now - datetime.timedelta(days=now.weekday())
    start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    start += datetime.timedelta(weeks=week_offset)
    return start, start + datetime.timedelta(days=7)

def get_month_range(month_offset: int = 0) -> tuple[datetime.datetime, datetime.datetime]:
    """Возвращает начало и конец месяца со смещением"""
    now = datetime.datetime.now().astimezone()
    
    # Определяем год и месяц с учетом смещения
    year = now.year
    month = now.month + month_offset
    
    # Корректируем год и месяц, если месяц вышел за пределы 1-12
    while month < 1:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1
    
    # Начало месяца: 1 число, 00:00:00
    start = datetime.datetime(year, month, 1, 0, 0, 0, 0, tzinfo=now.tzinfo)
    
    # Конец месяца: последний день месяца, 23:59:59.999999
    # Получаем количество дней в месяце
    last_day = calendar.monthrange(year, month)[1]
    end = datetime.datetime(year, month, last_day, 23, 59, 59, 999999, tzinfo=now.tzinfo)
    
    return start, end, month

def get_events(service, calendar_id: str, start: datetime.datetime, end: datetime.datetime) -> list[dict]:
    "Получает события за период"
    result = service.events().list(
        calendarId=calendar_id,
        timeMin=start.astimezone(datetime.timezone.utc).isoformat(),
        timeMax=end.astimezone(datetime.timezone.utc).isoformat(),
        singleEvents=True, orderBy='startTime'
    ).execute()
    
    return result.get('items', [])


#  ОБРАБОТКА ИНТЕРВАЛОВ 
def get_busy_intervals(events: list[dict], tz_info) -> list[tuple[datetime.datetime, datetime.datetime]]:
    "Извлекает занятые интервалы из событий"
    intervals = []
    for event in events:
        start, end = event.get('start', {}), event.get('end', {})
        if 'dateTime' not in start or 'dateTime' not in end:
            continue
        
        dt_start = parse_time(start['dateTime'], tz_info)
        dt_end = parse_time(end['dateTime'], tz_info)
        
        # Обрезаем по рабочему дню
        day_start = dt_start.replace(hour=WORK_START_HOUR, minute=0)
        day_end = dt_start.replace(hour=WORK_END_HOUR, minute=0)
        
        if dt_end > day_start and dt_start < day_end:
            intervals.append((max(dt_start, day_start), min(dt_end, day_end)))
    return intervals

def merge_intervals(intervals: list[tuple]) -> list[list]:
    "Объединяет пересекающиеся интервалы"
    if not intervals:
        return []
    intervals.sort()
    merged = [list(intervals[0])]
    for start, end in intervals[1:]:
        if start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged

def get_free_intervals(day_start: datetime.datetime, day_end: datetime.datetime, 
                       busy: list[list], min_minutes: int) -> list[tuple]:
    "Вычисляет свободные интервалы"
    free = []
    if not busy:
        free = [(day_start, day_end)]
    else:
        if day_start < busy[0][0]:
            free.append((day_start, busy[0][0]))
        for i in range(len(busy)-1):
            if busy[i][1] < busy[i+1][0]:
                free.append((busy[i][1], busy[i+1][0]))
        if busy[-1][1] < day_end:
            free.append((busy[-1][1], day_end))
    
    # Фильтруем по длительности
    return [(s, e) for s, e in free if (e - s).total_seconds() / 60 >= min_minutes]

#  ВЫВОД 
def format_interval(start: datetime.datetime, end: datetime.datetime) -> str:
    "Форматирует интервал без указания длительности"
    if start.strftime('%H:%M') == f"{WORK_START_HOUR:02d}:00" and end.strftime('%H:%M') == f"{WORK_END_HOUR:02d}:00":
        return "Весь день"
    return f"{start.strftime('%H:%M')}-{end.strftime('%H:%M')}"

def print_weekly_schedule(free_by_day: dict[int, list], week_start: datetime.datetime, title: str):
    "Выводит расписание на неделю"
    day_names = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
    print(f"\n{title}")
    print("=" * 70)
    
    has_free = False
    for i, name in enumerate(day_names):
        if i in free_by_day and free_by_day[i]:
            has_free = True
            day_date = week_start + datetime.timedelta(days=i)
            if SHOW_DATES:
                print(f"{name} ({day_date.strftime('%d.%m')})")
            else:
                print(f"{name}")
            for start, end in free_by_day[i]:
                print(format_interval(start, end))

    if not has_free:
        print("Нет свободных интервалов")
    print("=" * 70)

#  ОСНОВНЫЕ ФУНКЦИИ 
def get_week_schedule(service, calendar_id: str, week_offset: int = 0) -> dict[int, list]:
    "Возвращает расписание на указанную неделю"
    week_start, week_end = get_week_range(week_offset)
    events = get_events(service, calendar_id, week_start, week_end)
    tz_info = datetime.datetime.now().astimezone().tzinfo
    
    busy_by_day = {i: [] for i in range(7)}
    for event in events:
        for start, end in get_busy_intervals([event], tz_info):
            day = start.weekday()
            busy_by_day[day].append((start, end))
    
    # Объединяем интервалы и ищем свободные
    free_by_day = {}
    for day in range(7):
        day_date = week_start + datetime.timedelta(days=day)
        day_start = day_date.replace(hour=WORK_START_HOUR, minute=0)
        day_end = day_date.replace(hour=WORK_END_HOUR, minute=0)
        
        busy_merged = merge_intervals(busy_by_day[day])
        free = get_free_intervals(day_start, day_end, busy_merged, MIN_FREE_INTERVAL)
        if free:
            free_by_day[day] = free
    
    return free_by_day

def find_common_windows_next_and_two_ahead(service, calendar_id: str) -> dict[int, list]:
    "Находит общие свободные окна на следующей неделе и через одну."
    week_next = get_week_schedule(service, calendar_id, 1)   # Следующая неделя
    week_two = get_week_schedule(service, calendar_id, 2)    # Через одну неделю
    
    common = {}
    for day in range(7):
        if day in week_next and day in week_two:
            intersections = []
            for s1, e1 in week_next[day]:
                for s2, e2 in week_two[day]:
                    start1, end1 = s1.time(), e1.time()
                    start2, end2 = s2.time(), e2.time()
                    
                    intersect_start = max(start1, start2)
                    intersect_end = min(end1, end2)
                    
                    if intersect_start < intersect_end:
                        duration = (datetime.datetime.combine(datetime.date.today(), intersect_end) - 
                                  datetime.datetime.combine(datetime.date.today(), intersect_start)).total_seconds() / 60
                        if duration >= MIN_FREE_INTERVAL:
                            # Создаем интервал из первой недели
                            common_start = s1.replace(hour=intersect_start.hour, minute=intersect_start.minute)
                            common_end = s1.replace(hour=intersect_end.hour, minute=intersect_end.minute)
                            intersections.append((common_start, common_end))
            
            if intersections:
                common[day] = merge_intervals(intersections)
    
    return common

def display_events(events: list[dict], calendar_name: str):
    "Отображает события"
        
    print(f"\n{'='*70}\n {calendar_name} | {len(events)} событий\n{'='*70}")
    for i, e in enumerate(events, 1):
        start = e.get('start', {})
        time_str = parse_time(start['dateTime'], datetime.timezone.utc).strftime('%d.%m.%Y %H:%M') if 'dateTime' in start else start.get('date', 'Дата не указана')
        print(f"{i}. {e.get('summary', 'Без названия')}")
        print(f"Начало: {time_str}")
        if e.get('description'):
            print(f"Описание: {e.get('description')[:100]}")
        print(f"{'─'*50}")

def salary(events: list[dict]):
    "Считает зарплату"    
    salary = 0
    
    for i, event in enumerate(events, 1):
        if event.get('description'):
            try:
                salary += int(event.get('description'))
            except Exception as e:
                print(event.get('description'))
                print(f"\n Ошибка: {e}")
    return salary


def get_all_calendars(service) -> list[dict]:
    "Получает все календари"
    return service.calendarList().list().execute().get('items', [])

def main():
    print(f"Запуск парсера | Мин. интервал: {MIN_FREE_INTERVAL} мин")
    print(f"Режим: {'Общие окна на двух неделях' if SCHEDULE_MODE == 'two_weeks' else 'Только следующая неделя'}")
    
    try:
        creds = get_credentials()
        service = build('calendar', 'v3', credentials=creds)
        print("Подключено")
        
        calendars = get_all_calendars(service)
        if not calendars:
            print("Календари не найдены")
            return
        
        print(f" Найдено календарей: {len(calendars)}")

        
        # Выбираем календарь
        selected = None
        for i in calendars:
            if i['summary'] == 'Домашний':
                selected = i
                break
        
        if not selected:
             # Фолбэк, если календарь 'Домашний' не найден
            selected = calendars[0] if calendars else None


        cal_name = selected.get('summary', 'Календарь')
        cal_id = selected.get('id')
        
        # Показываем события
        week_start, _ = get_week_range(0)
        events = get_events(service, cal_id, week_start, week_start + datetime.timedelta(days=30))
        display_events(events[:15], cal_name)

        if SCHEDULE_MODE:  
            # Выводим расписание
            if SCHEDULE_MODE == 'next':
                # Только следующая неделя
                week_start_next, _ = get_week_range(1)
                schedule = get_week_schedule(service, cal_id, 1)
                print_weekly_schedule(
                    schedule,
                    week_start_next,
                    f" Свободное время в '{cal_name}' на следующей неделе"
                )
            elif SCHEDULE_MODE == 'two_weeks':
                # Общие окна на следующей неделе и через одну
                common_windows = find_common_windows_next_and_two_ahead(service, cal_id)
                if common_windows:
                    week_start_next, _ = get_week_range(1)
                    print_weekly_schedule(
                        common_windows,
                        week_start_next,
                        f" ОБЩИЕ ОКНА на следующей неделе и через одну (мин. {MIN_FREE_INTERVAL} мин)"
                    )
                else:
                    print(f"\n Нет общих окон длительностью {MIN_FREE_INTERVAL}+ минут на двух неделях")
        
        if MUNTH_SUM:
            month_ru = [
                "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
                "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
            ]
            month_start, month_end, month = get_month_range()
            events = get_events(service, cal_id, month_start, month_end)
            print(f'Зарплата за {month_ru[month - 1]}: {salary(events)}')

            now = datetime.datetime.now().astimezone()
            events = get_events(service, cal_id, month_start, now)
            print(f'Зарплата факт {month_ru[month - 1]}: {salary(events)}')

    except Exception as e:
        print(f"\n Ошибка: {e}")

if __name__ == '__main__':
    main()
