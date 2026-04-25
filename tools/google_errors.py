import json

from googleapiclient.errors import HttpError


def explain_google_http_error(exc: HttpError, api_name: str) -> RuntimeError:
    """Преобразует ошибку Google API в понятный текст"""
    status = getattr(exc.resp, "status", "unknown")
    raw_content = exc.content.decode("utf-8", errors="replace")
    message = raw_content
    reason = ""

    try:
        payload = json.loads(raw_content)
        error = payload.get("error", {})
        message = error.get("message", message)
        details = error.get("errors", [])
        if details:
            reason = details[0].get("reason", "")
    except json.JSONDecodeError:
        pass

    hint = ""
    if status == 403 and reason == "accessNotConfigured":
        hint = (
            f"\nПодсказка включите {api_name} в том же Google Cloud проекте "
            "где создан credentials json и повторите запуск через пару минут"
        )
    elif status == 403:
        hint = "\nПодсказка проверьте test users и scopes в OAuth consent screen"

    return RuntimeError(f"Ошибка Google {api_name} {status} {message}{hint}")
