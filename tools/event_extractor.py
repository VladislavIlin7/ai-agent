import json
import os
import re
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv


REQUIRED_FIELDS = {
    "has_event": False,
    "title": "",
    "date": "",
    "start_time": "",
    "end_time": "",
    "timezone": "Europe/Moscow",
    "description": "",
    "location": "",
    "source_email_subject": "",
    "source_email_from": "",
}

EVENT_KEYWORDS = (
    "meeting",
    "interview",
    "deadline",
    "webinar",
    "event",
    "call",
    "собеседован",
    "дедлайн",
    "встреч",
    "созвон",
)

RU_HOUR_WORDS = {
    "час": 1,
    "один": 1,
    "одного": 1,
    "два": 2,
    "двух": 2,
    "три": 3,
    "трех": 3,
    "четыре": 4,
    "четырех": 4,
    "пять": 5,
    "пяти": 5,
    "шесть": 6,
    "шести": 6,
    "семь": 7,
    "семи": 7,
    "восемь": 8,
    "восьми": 8,
    "девять": 9,
    "девяти": 9,
    "десять": 10,
    "десяти": 10,
    "одиннадцать": 11,
    "одиннадцати": 11,
    "двенадцать": 12,
    "двенадцати": 12,
}

MORNING_WORDS = ("утра", "утром")
DAY_WORDS = ("дня", "днем", "днём")
EVENING_WORDS = ("вечера", "вечером")
NIGHT_WORDS = ("ночи", "ночью")


def normalize_text(text: str) -> str:
    """Нормализует текст для простого поиска"""
    return text.lower().replace("ё", "е")


def looks_like_event_text(text: str) -> bool:
    """Проверяет текст по ключевым словам"""
    normalized = normalize_text(text)
    return any(keyword in normalized for keyword in EVENT_KEYWORDS)


class EventExtractor:
    """Инструмент для извлечения события из письма"""

    def __init__(self, use_llm: bool = True) -> None:
        """Читает настройки LLM из окружения"""
        load_dotenv()
        self.use_llm = use_llm
        self.api_key = os.getenv("API_KEY", "")
        self.base_url = self._normalize_base_url(os.getenv("BASE_URL", ""))
        self.model = os.getenv("MODEL", "")
        self.timeout = int(os.getenv("LLM_TIMEOUT", "60"))
        self.use_system_proxy = os.getenv("USE_SYSTEM_PROXY", "false").lower() in {
            "1",
            "true",
            "yes",
        }

    def extract_event(self, email: dict[str, Any]) -> dict[str, Any]:
        """Извлекает событие через LLM или fallback"""
        if self.use_llm and self.api_key and self.base_url and self.model:
            try:
                return self._extract_with_llm(email)
            except Exception as exc:
                print(f"LLM не сработала используется fallback {exc}")
        return self._fallback_extract(email)

    def test_connection(self) -> bool:
        """Проверяет подключение к LLM"""
        self._validate_llm_config()
        print(f"Проверка LLM модель {self.model} base url {self.base_url}")
        response = self._post_chat_completion(
            [
                {
                    "role": "system",
                    "content": "Return only JSON no markdown",
                },
                {
                    "role": "user",
                    "content": (
                        'Return exactly this JSON: {"has_event": false, "title": "", '
                        '"date": "", "start_time": "", "end_time": "", '
                        f'"timezone": "{DEFAULT_TIMEZONE}", "description": "", '
                        '"location": "", "source_email_subject": "", '
                        '"source_email_from": ""}'
                    ),
                },
            ],
        )
        content = response["choices"][0]["message"]["content"]
        self._parse_json(content)
        print("Подключение к LLM работает")
        return True

    def _extract_with_llm(self, email: dict[str, Any]) -> dict[str, Any]:
        """Отправляет письмо в LLM и нормализует ответ"""
        self._validate_llm_config()
        prompt = self._build_prompt(email)
        response = self._post_chat_completion(
            [
                {
                    "role": "system",
                    "content": (
                        "You extract calendar events from emails "
                        "Return only valid JSON no markdown"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
        content = response["choices"][0]["message"]["content"]
        event = self._parse_json(content)
        return self._normalize_event(event, email)

    def _post_chat_completion(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        """Вызывает OpenAI compatible chat completions"""
        session = requests.Session()
        session.trust_env = self.use_system_proxy
        url = f"{self.base_url}/chat/completions"

        try:
            response = session.post(
                url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "unknown"
            body = exc.response.text[:800] if exc.response is not None else ""
            raise RuntimeError(f"LLM HTTP ошибка {status} {body}") from exc
        except requests.RequestException as exc:
            raise RuntimeError(
                "Не удалось подключиться к LLM проверьте BASE_URL сеть и proxy "
                "если нужен системный proxy поставьте USE_SYSTEM_PROXY true"
            ) from exc

    def _validate_llm_config(self) -> None:
        """Проверяет обязательные настройки LLM"""
        missing = [
            name
            for name, value in {
                "API_KEY": self.api_key,
                "BASE_URL": self.base_url,
                "MODEL": self.model,
            }.items()
            if not value
        ]
        if missing:
            raise RuntimeError(f"Не хватает переменных LLM {', '.join(missing)}")

    def _normalize_base_url(self, value: str) -> str:
        """Приводит BASE_URL к корню v1"""
        url = value.strip().rstrip("/")
        if not url:
            return ""
        if not urlparse(url).scheme:
            url = f"https://{url}"
        if url.endswith("/chat/completions"):
            return url[: -len("/chat/completions")]
        if not url.endswith("/v1"):
            url = f"{url}/v1"
        return url

    def _build_prompt(self, email: dict[str, Any]) -> str:
        """Собирает prompt для извлечения JSON"""
        body = email.get("body", "")[:3500]
        today = datetime.now().date().isoformat()
        tomorrow = (datetime.now().date() + timedelta(days=1)).isoformat()
        day_after_tomorrow = (datetime.now().date() + timedelta(days=2)).isoformat()
        return f"""
You extract calendar events from emails.
Current date is {today}.
Default timezone is {DEFAULT_TIMEZONE}.

Return has_event true when the email contains any future meeting call interview deadline webinar event appointment or personal reminder.
Russian informal phrases are valid events.
Examples that must be events:
- "послезавтра ближе к восьми надо сходить на встречу" means date {day_after_tomorrow} and start_time 20:00
- "завтра в восемь утра собеседование" means date {tomorrow} and start_time 08:00
- "завтра в 8 вечера созвон" means date {tomorrow} and start_time 20:00
- "дедлайн в пятницу" is a deadline event

Relative date rules:
- "сегодня" means {today}
- "завтра" means {tomorrow}
- "послезавтра" and "после завтра" mean {day_after_tomorrow}

Time rules:
- If text says утра use morning time
- If text says дня use afternoon time
- If text says вечера use evening time
- If text says ночи use night time
- If text says "ближе к восьми" without уточнение prefer 20:00

If there is no future action with date or time set has_event false and leave other fields empty.
Return strictly this JSON object and no markdown:
{{
  "has_event": true/false,
  "title": "...",
  "date": "YYYY-MM-DD",
  "start_time": "HH:MM",
  "end_time": "HH:MM",
  "timezone": "{DEFAULT_TIMEZONE}",
  "description": "...",
  "location": "...",
  "source_email_subject": "...",
  "source_email_from": "..."
}}

Email subject: {email.get("subject", "")}
Email from: {email.get("from", "")}
Email snippet: {email.get("snippet", "")}
Email body:
{body}
""".strip()

    def _parse_json(self, content: str) -> dict[str, Any]:
        """Достает JSON из ответа модели"""
        content = content.strip()
        if content.startswith("```"):
            # Модель иногда возвращает JSON внутри markdown блока
            content = re.sub(r"^```(?:json)?", "", content).strip()
            content = re.sub(r"```$", "", content).strip()
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            raise ValueError("LLM не вернула JSON объект")
        return json.loads(match.group(0))

    def _normalize_event(self, event: dict[str, Any], email: dict[str, Any]) -> dict[str, Any]:
        """Добавляет отсутствующие поля события"""
        normalized = REQUIRED_FIELDS | event
        normalized["has_event"] = bool(normalized.get("has_event"))
        normalized["timezone"] = normalized.get("timezone") or DEFAULT_TIMEZONE
        normalized["source_email_subject"] = (
            normalized.get("source_email_subject") or email.get("subject", "")
        )
        normalized["source_email_from"] = (
            normalized.get("source_email_from") or email.get("from", "")
        )
        return normalized

    def _fallback_extract(self, email: dict[str, Any]) -> dict[str, Any]:
        """Извлекает событие простыми правилами"""
        text = f"{email.get('subject', '')}\n{email.get('snippet', '')}\n{email.get('body', '')}"
        if not looks_like_event_text(text):
            return self._normalize_event({"has_event": False}, email)

        date = self._find_date(text)
        start_time = self._find_time(text)
        title = email.get("subject", "Email event").strip()
        description = email.get("snippet") or "Событие найдено fallback режимом"
        event = {
            "has_event": True,
            "title": title,
            "date": date,
            "start_time": start_time,
            "end_time": "",
            "timezone": DEFAULT_TIMEZONE,
            "description": description,
            "location": self._find_location(text),
            "source_email_subject": email.get("subject", ""),
            "source_email_from": email.get("from", ""),
        }
        return self._normalize_event(event, email)

    def _find_date(self, text: str) -> str:
        """Ищет дату в простых форматах"""
        lower = normalize_text(text)
        today = datetime.now().date()
        if "послезавтра" in lower or "после завтра" in lower:
            return (today + timedelta(days=2)).isoformat()
        if "завтра" in lower:
            return (today + timedelta(days=1)).isoformat()

        iso_match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", text)
        if iso_match:
            return iso_match.group(1)

        european_match = re.search(r"\b(\d{1,2})[./](\d{1,2})[./](20\d{2})\b", text)
        if european_match:
            day, month, year = european_match.groups()
            return f"{year}-{int(month):02d}-{int(day):02d}"

        return (today + timedelta(days=1)).isoformat()

    def _find_time(self, text: str) -> str:
        """Ищет время в цифрах или словами"""
        lower = normalize_text(text)
        numeric_match = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", lower)
        if numeric_match:
            hour = int(numeric_match.group(1))
            minute = numeric_match.group(2)
            hour = self._apply_day_part(hour, lower)
            return f"{hour:02d}:{minute}"

        bare_hour_match = re.search(
            r"\b(?:в|к|около|примерно|ближе к)?\s*([1-9]|1[0-2])\s*"
            r"(?:час|часа|часам|часов)?\s*"
            r"(утра|утром|дня|днем|днём|вечера|вечером|ночи|ночью)\b",
            lower,
        )
        if bare_hour_match:
            hour = int(bare_hour_match.group(1))
            hour = self._apply_day_part(hour, lower)
            return f"{hour:02d}:00"

        for word, hour in RU_HOUR_WORDS.items():
            if re.search(rf"\b(?:к|около|примерно|ближе к)?\s*{word}\s*(?:час|часа|часам|часов)?\b", lower):
                hour = self._apply_day_part(hour, lower)
                return f"{hour:02d}:00"
        return ""

    def _apply_day_part(self, hour: int, lower_text: str) -> int:
        """Уточняет час по словам утро день вечер ночь"""
        if any(word in lower_text for word in MORNING_WORDS):
            if hour == 12:
                return 0
            return hour
        if any(word in lower_text for word in DAY_WORDS):
            if 1 <= hour <= 6:
                return hour + 12
            return hour
        if any(word in lower_text for word in EVENING_WORDS):
            if 1 <= hour <= 11:
                return hour + 12
            return hour
        if any(word in lower_text for word in NIGHT_WORDS):
            if hour == 12:
                return 0
            return hour
        if hour <= 11 and "ближе к" in lower_text:
            # Без уточнения ближе к восьми чаще означает вечер
            return hour + 12
        return hour

    def _find_location(self, text: str) -> str:
        """Ищет ссылку как место события"""
        url_match = re.search(r"https?://\S+", text)
        if url_match:
            return url_match.group(0).rstrip(".,)")
        return ""
