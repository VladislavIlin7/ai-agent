import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from tools.gmail_tool import SCOPES
from tools.google_errors import explain_google_http_error


class CalendarTool:
    """Инструмент для создания событий Calendar"""

    def __init__(
        self,
        demo: bool = False,
        auto_yes: bool = False,
        credentials_path: str = "credentials.json",
        token_path: str = "token.json",
    ) -> None:
        """Сохраняет настройки календаря"""
        self.demo = demo
        self.auto_yes = auto_yes
        self.credentials_path = Path(credentials_path)
        self.token_path = Path(token_path)

    def create_event(self, event: dict[str, Any]) -> dict[str, Any] | None:
        """Показывает preview и создает событие"""
        calendar_event = self._to_google_event(event)
        self._print_preview(calendar_event)

        if self.demo or not self.credentials_path.exists():
            print("Demo calendar tool реальное событие не создано")
            print(json.dumps(calendar_event, ensure_ascii=False, indent=2))
            return calendar_event

        if not self.auto_yes and not self._confirm():
            print("Пропущено пользователем")
            return None

        service = build("calendar", "v3", credentials=self._get_credentials())
        try:
            created = (
                service.events()
                .insert(calendarId="primary", body=calendar_event)
                .execute()
            )
        except HttpError as exc:
            raise explain_google_http_error(exc, "Google Calendar API") from exc

        print(f"Событие создано {created.get('htmlLink')}")
        return created

    def _to_google_event(self, event: dict[str, Any]) -> dict[str, Any]:
        """Преобразует JSON события в формат Google Calendar"""
        title = event.get("title") or "Email event"
        date = event.get("date")
        timezone = event.get("timezone") or "Europe/Moscow"
        start_time = event.get("start_time") or ""
        end_time = event.get("end_time") or ""
        description = self._build_description(event)

        google_event: dict[str, Any] = {
            "summary": title,
            "description": description,
            "location": event.get("location", ""),
        }

        if not date:
            date = datetime.now().date().isoformat()

        if not start_time:
            # Если время не найдено создаем событие на весь день
            google_event["start"] = {"date": date}
            google_event["end"] = {
                "date": (datetime.fromisoformat(date) + timedelta(days=1)).date().isoformat()
            }
            return google_event

        start_dt = datetime.fromisoformat(f"{date}T{start_time}:00")
        if end_time:
            end_dt = datetime.fromisoformat(f"{date}T{end_time}:00")
        else:
            # Если конец не найден ставим длительность один час
            end_dt = start_dt + timedelta(hours=1)

        google_event["start"] = {
            "dateTime": start_dt.isoformat(),
            "timeZone": timezone,
        }
        google_event["end"] = {
            "dateTime": end_dt.isoformat(),
            "timeZone": timezone,
        }
        return google_event

    def _build_description(self, event: dict[str, Any]) -> str:
        """Собирает описание события"""
        lines = [
            event.get("description", ""),
            "",
            f"Тема исходного письма {event.get('source_email_subject', '')}",
            f"Отправитель {event.get('source_email_from', '')}",
        ]
        return "\n".join(line for line in lines if line is not None).strip()

    def _print_preview(self, calendar_event: dict[str, Any]) -> None:
        """Печатает короткий preview события"""
        print("Preview события")
        print(f"  Название {calendar_event.get('summary')}")
        print(f"  Начало {calendar_event.get('start')}")
        print(f"  Конец {calendar_event.get('end')}")
        location = calendar_event.get("location")
        if location:
            print(f"  Место {location}")

    def _confirm(self) -> bool:
        """Спрашивает подтверждение создания"""
        answer = input("Создать событие в Google Calendar y N ").strip().lower()
        return answer in {"y", "yes", "д", "да"}

    def _get_credentials(self) -> Credentials:
        """Получает OAuth токен Google"""
        creds = None
        if self.token_path.exists():
            creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                # OAuth запускается только если токена еще нет
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.credentials_path),
                    SCOPES,
                )
                creds = flow.run_local_server(port=0)
            self.token_path.write_text(creds.to_json(), encoding="utf-8")
        return creds
