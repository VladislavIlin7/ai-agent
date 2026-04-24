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
    "timezone": "Europe/Amsterdam",
    "description": "",
    "location": "",
    "source_email_subject": "",
}

EVENT_KEYWORDS = (
    "meeting",
    "interview",
    "deadline",
    "webinar",
    "event",
    "call",
    "\u0441\u043e\u0431\u0435\u0441\u0435\u0434\u043e\u0432\u0430\u043d\u0438\u0435",
    "\u0434\u0435\u0434\u043b\u0430\u0439\u043d",
    "\u0432\u0441\u0442\u0440\u0435\u0447\u0430",
    "\u0441\u043e\u0437\u0432\u043e\u043d",
)


class EventExtractor:
    def __init__(self, use_llm: bool = True) -> None:
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
        if self.use_llm and self.api_key and self.base_url and self.model:
            try:
                return self._extract_with_llm(email)
            except Exception as exc:
                print(f"LLM extraction failed, using fallback extractor: {exc}")
        return self._fallback_extract(email)

    def test_connection(self) -> bool:
        self._validate_llm_config()
        print(f"Testing LLM: model={self.model}, base_url={self.base_url}")
        response = self._post_chat_completion(
            [
                {
                    "role": "system",
                    "content": "Return only JSON, no markdown.",
                },
                {
                    "role": "user",
                    "content": (
                        'Return exactly this JSON: {"has_event": false, "title": "", '
                        '"date": "", "start_time": "", "end_time": "", '
                        '"timezone": "Europe/Amsterdam", "description": "", '
                        '"location": "", "source_email_subject": ""}'
                    ),
                },
            ],
        )
        content = response["choices"][0]["message"]["content"]
        self._parse_json(content)
        print("LLM connection OK.")
        return True

    def _extract_with_llm(self, email: dict[str, Any]) -> dict[str, Any]:
        self._validate_llm_config()
        prompt = self._build_prompt(email)
        response = self._post_chat_completion(
            [
                {
                    "role": "system",
                    "content": (
                        "You extract calendar events from emails. "
                        "Return only valid JSON, no markdown."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
        content = response["choices"][0]["message"]["content"]
        event = self._parse_json(content)
        return self._normalize_event(event, email)

    def _post_chat_completion(self, messages: list[dict[str, str]]) -> dict[str, Any]:
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
            raise RuntimeError(f"LLM HTTP error {status}: {body}") from exc
        except requests.RequestException as exc:
            raise RuntimeError(
                "Could not connect to LLM. Check BASE_URL, network access, and proxy "
                "settings. If you need system proxy, set USE_SYSTEM_PROXY=true."
            ) from exc

    def _validate_llm_config(self) -> None:
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
            raise RuntimeError(f"Missing LLM env vars: {', '.join(missing)}")

    def _normalize_base_url(self, value: str) -> str:
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
        body = email.get("body", "")[:3500]
        return f"""
Extract one calendar event from this email.
If there is no event, set has_event to false and leave other fields empty.
Return strictly this JSON object:
{{
  "has_event": true/false,
  "title": "...",
  "date": "YYYY-MM-DD",
  "start_time": "HH:MM",
  "end_time": "HH:MM",
  "timezone": "Europe/Amsterdam",
  "description": "...",
  "location": "...",
  "source_email_subject": "..."
}}

Email subject: {email.get("subject", "")}
Email snippet: {email.get("snippet", "")}
Email body:
{body}
""".strip()

    def _parse_json(self, content: str) -> dict[str, Any]:
        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?", "", content).strip()
            content = re.sub(r"```$", "", content).strip()
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            raise ValueError("LLM did not return a JSON object")
        return json.loads(match.group(0))

    def _normalize_event(self, event: dict[str, Any], email: dict[str, Any]) -> dict[str, Any]:
        normalized = REQUIRED_FIELDS | event
        normalized["has_event"] = bool(normalized.get("has_event"))
        normalized["source_email_subject"] = (
            normalized.get("source_email_subject") or email.get("subject", "")
        )
        return normalized

    def _fallback_extract(self, email: dict[str, Any]) -> dict[str, Any]:
        text = f"{email.get('subject', '')}\n{email.get('snippet', '')}\n{email.get('body', '')}"
        lower = text.lower()
        has_event = any(keyword in lower for keyword in EVENT_KEYWORDS)
        if not has_event:
            return self._normalize_event({"has_event": False}, email)

        date = self._find_date(text)
        start_time = self._find_time(text)
        title = email.get("subject", "Email event").strip()
        description = email.get("snippet") or "Extracted from email in fallback mode."
        event = {
            "has_event": True,
            "title": title,
            "date": date,
            "start_time": start_time,
            "end_time": "",
            "timezone": "Europe/Amsterdam",
            "description": description,
            "location": self._find_location(text),
            "source_email_subject": email.get("subject", ""),
        }
        return self._normalize_event(event, email)

    def _find_date(self, text: str) -> str:
        iso_match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", text)
        if iso_match:
            return iso_match.group(1)

        european_match = re.search(r"\b(\d{1,2})[./](\d{1,2})[./](20\d{2})\b", text)
        if european_match:
            day, month, year = european_match.groups()
            return f"{year}-{int(month):02d}-{int(day):02d}"

        tomorrow = datetime.now().date() + timedelta(days=1)
        return tomorrow.isoformat()

    def _find_time(self, text: str) -> str:
        match = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", text)
        if match:
            return f"{int(match.group(1)):02d}:{match.group(2)}"
        return ""

    def _find_location(self, text: str) -> str:
        url_match = re.search(r"https?://\S+", text)
        if url_match:
            return url_match.group(0).rstrip(".,)")
        return ""
