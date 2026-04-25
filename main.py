import argparse
import sys

from agent import EmailToCalendarAgent
from tools.event_extractor import EventExtractor


def configure_output_encoding() -> None:
    """Настраивает вывод в UTF 8 для Windows"""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def parse_args() -> argparse.Namespace:
    """Читает аргументы командной строки"""
    parser = argparse.ArgumentParser(
        description="CLI агент для переноса событий из Gmail в Google Calendar",
    )
    parser.add_argument(
        "task",
        nargs="?",
        default="Проверь последние письма и добавь найденные события в календарь",
        help="Задача для агента на естественном языке",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Использовать тестовые письма и не создавать реальные события",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Создавать события без подтверждения",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=10,
        help="Сколько последних писем читать максимум 10",
    )
    parser.add_argument(
        "--test-llm",
        action="store_true",
        help="Проверить подключение к LLM и выйти",
    )
    return parser.parse_args()


def main() -> int:
    """Запускает CLI приложение"""
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
        print(f"Ошибка {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
