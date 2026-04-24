import argparse
import sys

from agent import EmailToCalendarAgent
from tools.event_extractor import EventExtractor


def configure_output_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Email-to-Calendar AI Agent CLI",
    )
    parser.add_argument(
        "task",
        nargs="?",
        default="Проверь последние письма и добавь найденные события в календарь",
        help="Natural language task for the agent.",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Use sample emails and do not create real Google Calendar events.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Create calendar events without asking for confirmation.",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=10,
        help="Maximum number of recent Gmail messages to read. Capped at 10.",
    )
    parser.add_argument(
        "--test-llm",
        action="store_true",
        help="Check LLM connection and exit.",
    )
    return parser.parse_args()


def main() -> int:
    configure_output_encoding()
    args = parse_args()
    try:
        if args.test_llm:
            EventExtractor().test_connection()
            return 0

        agent = EmailToCalendarAgent(
            demo=args.demo,
            auto_yes=args.yes,
            max_results=min(args.max_results, 10),
        )
        agent.run(args.task)
        return 0
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
