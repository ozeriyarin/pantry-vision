"""Every owner-facing Hebrew string, per contracts/bot-commands.md."""

from collections.abc import Iterable

from pantry.domain.models import Location

LOCATION_HE = {Location.FRIDGE: "מקרר", Location.FREEZER: "מקפיא", Location.PANTRY: "מזווה"}


def in_location(location: Location) -> str:
    return f"ב{LOCATION_HE[location]}"


def item_line(name_he: str, count: int, uncertain: bool = False) -> str:
    return f"{name_he} ×{count}" + (" ?" if uncertain else "")


def photo_reply(location: Location, lines: Iterable[str], not_checked: int = 0) -> str:
    parts = [f"{in_location(location)}:", *lines]
    if not_checked:
        parts.append(f"{not_checked} פריטים לא נבדקו שוב.")
    parts.append(f'כשסיימתם לצלם את כל ה{LOCATION_HE[location]}, שלחו "סיימתי".')
    return "\n".join(parts)


def no_food() -> str:
    return "לא מצאתי מוצרים בתמונה."


def unclear_photo() -> str:
    return "התמונה לא ברורה, אפשר לצלם שוב?"


def updated(name_he: str, count: int) -> str:
    return f"עודכן: {item_line(name_he, count)}"


def unknown_item(name: str) -> str:
    return f'לא מכיר "{name}". להוסיף כסוג מוצר חדש?'


def session_closed(location: Location, zeroed: Iterable[str]) -> str:
    zeroed = list(zeroed)
    if not zeroed:
        return "שום דבר לא נגמר"
    return "\n".join([f"נגמרו {in_location(location)}:", *zeroed])


def not_understood() -> str:
    return 'לא הבנתי. אפשר לשלוח תמונה, לתקן ("ביצים 4", "אין חלב") או לשאול "מה יש לי?"'


def inventory(groups: dict[Location, list[str]]) -> str:
    if not any(groups.values()):
        return "אין כלום במלאי."
    blocks = [f"{in_location(loc)}:\n" + "\n".join(lines) for loc, lines in groups.items() if lines]
    return "\n\n".join(blocks)


def has_item(name_he: str, count: int, location: Location) -> str:
    return f"כן, {item_line(name_he, count)} {in_location(location)}"


def no_item(name_he: str) -> str:
    return f"אין {name_he}"


def morning(run_out: Iterable[tuple[str, Location]]) -> str:
    run_out = list(run_out)
    if not run_out:
        return "בוקר טוב, הכול בסדר."
    lines = [f"{name} ({LOCATION_HE[loc]})" for name, loc in run_out]
    return "\n".join(["בוקר טוב. נגמרו מאתמול:", *lines])


def error() -> str:
    return "משהו השתבש, אפשר לנסות שוב?"


YES, NO = "כן", "לא"
CONFIRM, REMOVE = "✓", "✗"
