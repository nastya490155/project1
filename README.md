# CalendarAnalyzer

Анализатор Google Calendar для поиска свободного времени и подсчета дохода.

## Авторы

- Клиперт Георгий
- Анисова Анастасия
- Колесникова Лидия

## Описание

Проект анализирует Google Calendar и позволяет:
- Находить свободные интервалы в расписании
- Анализировать загруженность на неделях
- Находить общие свободные окна для встреч
- Подсчитывать доход на основе описаний событий

## Установка

1. Установите зависимости:
```bash
pip install google-auth google-auth-oauthlib google-api-python-client
```

2. Настройте Google Calendar API:
   - Создайте проект в [Google Cloud Console](https://console.cloud.google.com/)
   - Включите Google Calendar API
   - Скачайте файл credentials (OAuth 2.0 Client ID)
   - Сохраните как `credentials.json`


## Конфигурация

В начале `main.py` настройте параметры:

```python
WORK_START_HOUR = 10          # Начало рабочего дня
WORK_END_HOUR = 22            # Конец рабочего дня
MIN_FREE_INTERVAL = 60        # Минимальный интервал (минуты)
SCHEDULE_MODE = 'next'        # 'next' | 'two_weeks' | False
MUNTH_SUM = True              # Подсчет дохода (True/False)
SHOW_DATES = False            # Показывать даты (True/False)
TARGET_CALENDAR_NAME = 'Домашний'  # Имя календаря
```

## Режимы работы

**SCHEDULE_MODE:**
- `'next'` — свободное время на следующей неделе
- `'two_weeks'` — общие окна на двух неделях
- `False` — не показывать расписание
