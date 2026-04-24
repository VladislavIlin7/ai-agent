from tools.calendar_tool import CalendarTool
from tools.event_extractor import EventExtractor
from tools.gmail_tool import GmailTool


class EmailToCalendarAgent:
    """Small tool-calling agent for the hackathon MVP."""

    def __init__(self, demo: bool, auto_yes: bool, max_results: int = 10) -> None:
        self.demo = demo
        self.auto_yes = auto_yes
        self.max_results = min(max_results, 10)
        self.gmail_tool = GmailTool(demo=demo)
        self.extractor = EventExtractor(use_llm=not demo)
        self.calendar_tool = CalendarTool(demo=demo, auto_yes=auto_yes)

    def run(self, task: str) -> list[dict]:
        print(f"Task: {task}")
        print("Agent plan: read Gmail -> extract events with LLM -> create Calendar events")

        emails = self.gmail_tool.read_recent_emails(max_results=self.max_results)
        if not emails:
            print("No candidate emails found.")
            return []

        created_events: list[dict] = []
        for index, email in enumerate(emails, start=1):
            subject = email.get("subject", "(no subject)")
            print(f"\n[{index}/{len(emails)}] Processing email: {subject}")

            event = self.extractor.extract_event(email)
            if not event.get("has_event"):
                print("No event found.")
                continue

            result = self.calendar_tool.create_event(event)
            if result:
                created_events.append(result)

        print(f"\nDone. Events handled: {len(created_events)}")
        return created_events
