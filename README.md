Track: A

# Email-to-Calendar AI Agent

CLI MVP: агент читает последние письма из Gmail, находит события и создает записи в Google Calendar.

## Что умеет

- читает до 10 последних писем через Gmail API;
- фильтрует письма по словам `meeting`, `interview`, `deadline`, `webinar`, `event`, `call`, `собеседование`, `дедлайн`, `встреча`, `созвон`;
- извлекает событие через OpenAI-compatible LLM (`API_KEY`, `BASE_URL`, `MODEL`);
- показывает preview события перед созданием;
- создает событие в Google Calendar;
- работает в demo mode без Google OAuth.

## Tools

- `GmailTool` — читает Gmail или `examples/sample_emails.json`.
- `EventExtractor` — отправляет текст письма в LLM и ожидает строгий JSON.
- `CalendarTool` — создает событие в Google Calendar или печатает JSON в demo mode.

## Установка

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Создайте `.env` по примеру:

```env
API_KEY=your_llm_api_key_here
BASE_URL=https://your-openai-compatible-endpoint/v1
MODEL=qwen3.5-122b
LLM_TIMEOUT=60
USE_SYSTEM_PROXY=false
```

Проверка LLM:

```bash
python main.py --test-llm
```

## Demo запуск

```bash
python main.py "Проверь последние письма и добавь события в календарь" --demo
```

В demo mode агент берет письма из `examples/sample_emails.json` и не создает реальные события.

## Реальный запуск

Положите Google OAuth файл в корень проекта:

```text
credentials.json
```

Затем запустите:

```bash
python main.py "Проверь последние письма и добавь события в календарь" --yes
```

При первом запуске откроется Google OAuth. После входа появится локальный `token.json`.

## Google OAuth

Нужно включить в Google Cloud Console:

- Gmail API;
- Google Calendar API.

OAuth Client ID должен быть типа `Desktop app`.

Scopes:

- `https://www.googleapis.com/auth/gmail.readonly`
- `https://www.googleapis.com/auth/calendar.events`

`.env`, `credentials.json` и `token.json` находятся в `.gitignore`.

## Ограничения MVP

- максимум 10 писем за запуск;
- одно событие из одного письма;
- нет дедупликации;
- нет обработки переносов и отмен;
- fallback extractor понимает только простые даты;
- полный текст писем не логируется, но фрагмент письма отправляется в LLM.

## Пример вывода

```text
Task: Проверь последние письма и добавь события в календарь
Agent plan: read Gmail -> extract events with LLM -> create Calendar events
Gmail tool read 10 messages, candidates: 2

[1/2] Processing email: Interview with Data Platform team
Calendar preview:
  Title: Interview with Data Platform team
  Start: {'dateTime': '2026-04-28T14:30:00', 'timeZone': 'Europe/Amsterdam'}
  End: {'dateTime': '2026-04-28T15:30:00', 'timeZone': 'Europe/Amsterdam'}
Created event: https://calendar.google.com/...
```
