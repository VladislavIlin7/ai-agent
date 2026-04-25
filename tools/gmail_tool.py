import base64
import json
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from tools.event_extractor import looks_like_event_text
from tools.google_errors import explain_google_http_error


SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]

class GmailTool:
    """Инструмент для чтения писем Gmail"""

    def __init__(
        self,
        demo: bool = False,
        credentials_path: str = "credentials.json",
        token_path: str = "token.json",
        sample_path: str = "examples/sample_emails.json",
    ) -> None:
        """Сохраняет пути и режим запуска"""
        self.demo = demo
        self.credentials_path = Path(credentials_path)
        self.token_path = Path(token_path)
        self.sample_path = Path(sample_path)

    def read_recent_emails(self, max_results: int = 10) -> list[dict[str, Any]]:
        """Читает последние письма и оставляет кандидаты на событие"""
        max_results = min(max_results, 10)
        if self.demo or not self.credentials_path.exists():
            if not self.demo:
                print("credentials json не найден включен demo режим")
            return self._read_sample_emails(max_results)

        service = build("gmail", "v1", credentials=self._get_credentials())
        try:
            response = (
                service.users()
                .messages()
                .list(userId="me", maxResults=max_results, labelIds=["INBOX"])
                .execute()
            )
        except HttpError as exc:
            raise explain_google_http_error(exc, "Gmail API") from exc

        messages = response.get("messages", [])
        emails: list[dict[str, Any]] = []

        for message in messages[:max_results]:
            try:
                payload = (
                    service.users()
                    .messages()
                    .get(userId="me", id=message["id"], format="full")
                    .execute()
                )
            except HttpError as exc:
                raise explain_google_http_error(exc, "Gmail API") from exc

            email = self._parse_message(payload)
            if self._looks_like_event(email):
                emails.append(email)

        print(f"Gmail tool прочитал писем {len(messages[:max_results])} кандидатов {len(emails)}")
        return emails

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

    def _read_sample_emails(self, max_results: int) -> list[dict[str, Any]]:
        """Читает тестовые письма для demo режима"""
        data = json.loads(self.sample_path.read_text(encoding="utf-8"))
        emails = data[:max_results]
        candidates = [email for email in emails if self._looks_like_event(email)]
        print(f"Demo Gmail tool загрузил писем {len(emails)} кандидатов {len(candidates)}")
        return candidates

    def _looks_like_event(self, email: dict[str, Any]) -> bool:
        """Проверяет письмо по ключевым словам"""
        text = f"{email.get('subject', '')}\n{email.get('snippet', '')}\n{email.get('body', '')}".lower()
        return looks_like_event_text(text)

    def _parse_message(self, message: dict[str, Any]) -> dict[str, Any]:
        """Преобразует Gmail message в простой словарь"""
        payload = message.get("payload", {})
        headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}
        body = self._extract_body(payload)
        date_header = headers.get("date", "")
        received_at = None
        if date_header:
            try:
                received_at = parsedate_to_datetime(date_header).isoformat()
            except (TypeError, ValueError):
                received_at = date_header

        return {
            "id": message.get("id"),
            "subject": headers.get("subject", "без темы"),
            "from": headers.get("from", ""),
            "received_at": received_at,
            "snippet": message.get("snippet", ""),
            "body": body[:6000],
        }

    def _extract_body(self, payload: dict[str, Any]) -> str:
        """Достает текстовую часть письма"""
        parts = payload.get("parts", [])
        if parts:
            for part in parts:
                if part.get("mimeType") == "text/plain":
                    return self._decode_body(part)
            for part in parts:
                # Gmail может хранить тело письма во вложенных частях
                nested = self._extract_body(part)
                if nested:
                    return nested
        return self._decode_body(payload)

    def _decode_body(self, part: dict[str, Any]) -> str:
        """Декодирует base64 тело письма"""
        data = part.get("body", {}).get("data")
        if not data:
            return ""
        decoded = base64.urlsafe_b64decode(data.encode("utf-8"))
        return decoded.decode("utf-8", errors="replace")
