from tools.calendar_tool import CalendarTool
from tools.event_extractor import EventExtractor
from tools.gmail_tool import GmailTool


class EmailToCalendarAgent:
    """Агент который вызывает Gmail LLM и Calendar tools"""

    def __init__(self, demo: bool, auto_yes: bool, max_results: int = 10) -> None:
        """Создает инструменты агента"""
        self.demo = demo
        self.auto_yes = auto_yes
        self.max_results = min(max_results, 10)
        self.gmail_tool = GmailTool(demo=demo)
        self.extractor = EventExtractor(use_llm=not demo)
        self.calendar_tool = CalendarTool(demo=demo, auto_yes=auto_yes)

    def run(self, task: str) -> list[dict]:
        """Выполняет задачу пользователя"""
        print(f"Задача {task}")
        print("План агента читать Gmail затем извлечь события через LLM затем создать события в Calendar")

        emails = self.gmail_tool.read_recent_emails(max_results=self.max_results)
        if not emails:
            print("Письма с возможными событиями не найдены")
            return []

        created_events: list[dict] = []
        for index, email in enumerate(emails, start=1):
            subject = email.get("subject", "без темы")
            print(f"\n[{index}/{len(emails)}] Обработка письма {subject}")

            event = self.extractor.extract_event(email)
            if not event.get("has_event"):
                print("Событие не найдено")
                continue

            result = self.calendar_tool.create_event(event)
            if result:
                created_events.append(result)

        print(f"\nГотово обработано событий {len(created_events)}")
        return created_events
