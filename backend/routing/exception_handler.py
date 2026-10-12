from rest_framework.views import exception_handler

STATUS_CODES = {
    400: "validation_error",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    415: "unsupported_media_type",
    422: "unprocessable_entity",
    429: "rate_limited",
    500: "server_error",
    502: "provider_error",
    503: "service_unavailable",
}


def _summarize(errors) -> str:
    parts = []
    if isinstance(errors, dict):
        items = errors.items()
    else:
        items = ((None, errors),)
    for field, value in items:
        text = "; ".join(str(item) for item in value) if isinstance(value, (list, tuple)) else str(value)
        if field and field != "non_field_errors":
            parts.append(f"{field}: {text}")
        else:
            parts.append(text)
    return " ".join(parts) or "The request could not be processed."


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None

    data = response.data
    details = {}
    if isinstance(data, dict) and "detail" in data:
        message = str(data["detail"])
    elif isinstance(data, dict):
        message = _summarize(data)
        details = data
    elif isinstance(data, list):
        message = _summarize(data)
        details = {"errors": data}
    else:
        message = str(data)

    response.data = {
        "error": {
            "code": STATUS_CODES.get(response.status_code, "error"),
            "message": message,
            "details": details,
        }
    }
    return response
