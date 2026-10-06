"""Helpers shared by the view modules."""


def _messages(errors, prefix: str = "") -> list[str]:
    """Flatten nested serializer errors (dicts keyed by field or list index, lists) to text."""
    if isinstance(errors, dict):
        return [
            message
            for key, value in errors.items()
            for message in _messages(
                value, f"{prefix}{key}: " if not str(key).isdigit() else prefix
            )
        ]
    if isinstance(errors, list | tuple):
        return [message for item in errors for message in _messages(item, prefix)]
    return [f"{prefix}{errors}"]


def validation_detail(errors: dict) -> dict[str, str]:
    """A serializer's field errors as the API's `{"detail": ...}` error body."""
    return {"detail": "; ".join(_messages(errors))}
