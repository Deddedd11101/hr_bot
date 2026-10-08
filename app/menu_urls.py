from urllib.parse import urlsplit


def is_valid_menu_url(value: str | None) -> bool:
    if not value or len(value) > 2048 or "\\" in value:
        return False
    if any(char.isspace() or ord(char) < 32 for char in value):
        return False
    try:
        parsed = urlsplit(value)
        return (
            parsed.scheme in {"http", "https"}
            and bool(parsed.hostname)
            and parsed.port != 0
            and "@" not in parsed.netloc
            and not parsed.username
            and not parsed.password
        )
    except ValueError:
        return False
