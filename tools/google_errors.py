import json

from googleapiclient.errors import HttpError


def explain_google_http_error(exc: HttpError, api_name: str) -> RuntimeError:
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
            f"\nHint: enable {api_name} in the same Google Cloud project that owns "
            "credentials.json, wait a few minutes, then run the command again."
        )
    elif status == 403:
        hint = "\nHint: check OAuth consent screen test users and requested scopes."

    return RuntimeError(f"Google {api_name} error {status}: {message}{hint}")
