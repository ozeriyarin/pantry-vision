"""Every owner-facing Hebrew string, per contracts/bot-commands.md."""

from collections.abc import Iterable

CORRECTION_HINT = 'לתיקון שלחו למשל "ביצים 4", "אין חלב" או "להוסיף חומוס", או לחצו ✓/✗.'


# Location arguments below are Hebrew display names from the location catalogue.


def in_location(place: str) -> str:
    return f"ב{place}"


def item_line(name_he: str, count: int, uncertain: bool = False) -> str:
    return f"{name_he} ×{count}" + (" ?" if uncertain else "")


def photo_reply(place: str, lines: Iterable[str], not_checked: int = 0) -> str:
    parts = [f"{in_location(place)}:", *lines]
    if not_checked:
        parts.append(f"{not_checked} פריטים לא נבדקו שוב.")
    parts.append(CORRECTION_HINT)
    parts.append(f'כשסיימתם לצלם את כל ה{place}, שלחו "סיימתי".')
    return "\n".join(parts)


def no_food() -> str:
    return "לא מצאתי מוצרים בתמונה."


def unclear_photo() -> str:
    return "התמונה לא ברורה, אפשר לצלם שוב?"


def updated(name_he: str, count: int) -> str:
    return f"עודכן: {item_line(name_he, count)}"


def unknown_item(name: str) -> str:
    return f'לא מכיר "{name}". להוסיף כסוג מוצר חדש?'


def session_closed(place: str, zeroed: Iterable[str]) -> str:
    zeroed = list(zeroed)
    if not zeroed:
        return "שום דבר לא נגמר"
    return "\n".join([f"נגמרו {in_location(place)}:", *zeroed])


def updated_many(lines: list[str]) -> list[str]:
    return ["עודכן:", *lines] if lines else []


def not_understood_line(line: str) -> str:
    return f'לא הבנתי: "{line}"'


def unknown_items(names: list[str], suggestions: dict[str, str] | None = None) -> str:
    suggestions = suggestions or {}
    if not suggestions:
        if len(names) == 1:
            return unknown_item(names[0])
        quoted = ", ".join(f'"{n}"' for n in names)
        return f"לא מכיר: {quoted}. להוסיף כסוגי מוצרים חדשים?"
    if len(names) == 1:
        return f'לא מכיר "{names[0]}". התכוונת ל{suggestions[names[0]]}?'
    lines = [
        f'"{n}" - התכוונת ל{suggestions[n]}?' if n in suggestions else f'"{n}" - פריט חדש' for n in names
    ]
    return "\n".join(["לא מכיר:", *lines, "לאשר?"])


def no_open_session() -> str:
    return "אין צילום פתוח לסגור."


def question_expired() -> str:
    return "השאלה כבר לא בתוקף, אפשר לשלוח שוב."


def not_added() -> str:
    return "בסדר, לא הוספתי."


def stale_button() -> str:
    return "הכפתור כבר לא בתוקף."


def not_understood() -> str:
    return 'לא הבנתי. אפשר לשלוח תמונה, לתקן ("ביצים 4", "אין חלב") או לשאול "מה יש לי?"'


def inventory(groups: dict[str, list[str]]) -> str:
    if not any(groups.values()):
        return "אין כלום במלאי."
    blocks = [f"{in_location(place)}:\n" + "\n".join(lines) for place, lines in groups.items() if lines]
    return "\n\n".join(blocks)


def has_item(name_he: str, count: int, place: str) -> str:
    return f"כן, {item_line(name_he, count)} {in_location(place)}"


def no_item(name_he: str) -> str:
    return f"אין {name_he}"


def morning(run_out: Iterable[tuple[str, str]]) -> str:
    run_out = list(run_out)
    if not run_out:
        return "בוקר טוב, הכול בסדר."
    lines = [f"{name} ({place})" for name, place in run_out]
    return "\n".join(["בוקר טוב. נגמרו מאתמול:", *lines])


def location_added(name: str) -> str:
    return f'נוסף מיקום: {name}. אפשר לשלוח תמונה עם הכיתוב "{name}".'


def location_exists(name: str) -> str:
    return f'כבר יש מיקום בשם "{name}".'


def locations(names: Iterable[str]) -> str:
    return "מיקומים: " + ", ".join(names)


def error() -> str:
    return "משהו השתבש, אפשר לנסות שוב?"


YES, NO = "כן", "לא"
NEW, CANCEL = "פריט חדש", "ביטול"
CONFIRM, REMOVE = "✓", "✗"
