Track: A

# Email-to-Calendar AI Agent

CLI MVP для хакатона: агент читает последние письма из Gmail, находит письма с потенциальными событиями, извлекает параметры события через LLM и создает событие в Google Calendar.

## Что делает агент

1. Получает последние 10 писем из Gmail или demo fixture.
2. Отбирает письма по словам: `meeting`, `interview`, `deadline`, `webinar`, `event`, `call`, `собеседование`, `дедлайн`, `встреча`, `созвон`.
3. Передает текст письма в OpenAI-compatible LLM API: `API_KEY`, `BASE_URL`, `MODEL`.
4. Ожидает строгий JSON с датой, временем, названием, описанием, локацией и темой исходного письма.
5. Показывает preview и создает событие в Google Calendar.

## Tools

- `GmailTool` в `tools/gmail_tool.py`: читает максимум 10 последних писем через Gmail API или `examples/sample_emails.json` в demo mode.
- `CalendarTool` в `tools/calendar_tool.py`: создает события через Google Calendar API или печатает JSON события в demo mode.
- `EventExtractor` в `tools/event_extractor.py`: вызывает OpenAI-compatible LLM API и нормализует JSON события.

## Установка

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Скопируйте `.env.example` в `.env` и заполните переменные для вашей OpenAI-compatible LLM. Для Qwen/LiteLLM endpoint нужен ключ именно от этого endpoint; Gemini key или OpenAI key здесь не подойдут.

```env
API_KEY=your_llm_api_key_here
BASE_URL=https://your-openai-compatible-endpoint/v1
MODEL=qwen3.5-122b
LLM_TIMEOUT=60
USE_SYSTEM_PROXY=false
```

Проверить LLM отдельно, без Gmail и Calendar:

```bash
python main.py --test-llm
```

Если ваш провайдер требует системный proxy, поставьте `USE_SYSTEM_PROXY=true`. В обычном режиме лучше оставить `false`, чтобы случайные proxy-переменные Windows не ломали подключение.

## Запуск в demo mode

Одна команда после установки зависимостей:

```bash
python main.py "Проверь последние письма и добавь события в календарь" --demo
```

Demo mode работает offline: использует простой fallback extractor и не создает реальные события в календаре.

## Реальный запуск с Gmail/Calendar API

Перед запуском положите OAuth-файл Google в корень проекта:

```text
credentials.json
```

При первом запуске откроется Google OAuth flow. В браузере войдите в нужную Google-почту и разрешите доступ к Gmail readonly и Google Calendar events. После успешного входа локально появится `token.json`; именно он привязывает проект к выбранной почте и календарю. По умолчанию события создаются в primary calendar этого аккаунта.

```bash
python main.py "Проверь последние письма и добавь события в календарь" --yes
```

Без `--yes` агент спросит подтверждение перед созданием каждого события.

## Как получить credentials.json

1. Откройте Google Cloud Console.
2. Создайте проект или выберите существующий.
3. Включите Gmail API и Google Calendar API.
4. Создайте OAuth Client ID типа Desktop app.
5. Скачайте JSON и положите его в корень проекта как `credentials.json`.
6. При первом реальном запуске агент откроет OAuth flow и сохранит локальный `token.json`.

Используемые scopes:

- `https://www.googleapis.com/auth/gmail.readonly`
- `https://www.googleapis.com/auth/calendar.events`

`credentials.json`, `token.json` и `.env` добавлены в `.gitignore`.

## Ограничения MVP

- Читает только последние 10 писем.
- Извлекает одно событие из одного письма.
- Не логирует полный текст писем, но отправляет ограниченный фрагмент тела письма в LLM.
- Если LLM недоступна, fallback extractor подходит только для demo и простых дат.
- Повторные события, конфликты календаря и дедупликация не реализованы.

## Пример вывода

```text
Task: Проверь последние письма и добавь события в календарь
Agent plan: read Gmail -> extract events with LLM -> create Calendar events
Demo Gmail tool loaded 4 sample emails, candidates: 3

[1/3] Processing email: Interview with Data Platform team
Calendar preview:
  Title: Interview with Data Platform team
  Start: {'dateTime': '2026-04-28T14:30:00', 'timeZone': 'Europe/Amsterdam'}
  End: {'dateTime': '2026-04-28T15:30:00', 'timeZone': 'Europe/Amsterdam'}
Demo calendar tool: real Google Calendar event was not created.
```
