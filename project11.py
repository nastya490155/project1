#!/usr/bin/env python3
"""
Парсер Google Calendar API - Этап 1: Подключение и базовые утилиты
"""

import datetime
import os.path
import pickle
from typing import List, Dict, Any, Tuple, Optional
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Конфигурация
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
WORK_START_HOUR, WORK_END_HOUR = 10, 22
MIN_FREE_INTERVAL = 60  # минут

# ============ АУТЕНТИФИКАЦИЯ ============
def get_credentials():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)

    path = 'client_secret_1044780173531-9n79dtbhfs2tthk6b555mtgt3gua92gf.apps.googleusercontent.com.json'
    
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

# ============ ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ============
def parse_time(dt_str: str, tz_info) -> datetime.datetime:
    """Парсит время из строки Google Calendar"""
    if dt_str.endswith('Z'):
        dt_str = dt_str[:-1] + '+00:00'
    dt = datetime.datetime.fromisoformat(dt_str)
    return dt.astimezone(tz_info) if dt.tzinfo else dt.replace(tzinfo=datetime.timezone.utc).astimezone(tz_info)

def get_week_range(week_offset: int = 0) -> Tuple[datetime.datetime, datetime.datetime]:
    """Возвращает начало и конец недели со смещением"""
    now = datetime.datetime.now().astimezone()
    start = now - datetime.timedelta(days=now.weekday())
    start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    start += datetime.timedelta(weeks=week_offset)
    return start, start + datetime.timedelta(days=7)

def get_events(service, calendar_id: str, start: datetime.datetime, end: datetime.datetime) -> List[Dict]:
    """Получает события за период"""
    try:
        result = service.events().list(
            calendarId=calendar_id,
            timeMin=start.astimezone(datetime.timezone.utc).isoformat(),
            timeMax=end.astimezone(datetime.timezone.utc).isoformat(),
            singleEvents=True, orderBy='startTime'
        ).execute()
        
        return result.get('items', [])
    except HttpError as e:
        print(f'Ошибка API: {e}')
        return []

# ============ MAIN ============
def main():
    print("🔐 Запуск парсера (Этап 1: Проверка подключения)")
    
    try:
        creds = get_credentials()
        service = build('calendar', 'v3', credentials=creds)
        print("✅ Успешное подключение к Google Calendar API")
        
        # Тестовый запрос событий на текущую неделю
        week_start, week_end = get_week_range(0)
        events = get_events(service, 'primary', week_start, week_end)
        print(f"📅 Получено событий за текущую неделю: {len(events)}")
        
    except FileNotFoundError as e:
        print(f"\n❌ {e}")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        raise

if __name__ == '__main__':
    main()