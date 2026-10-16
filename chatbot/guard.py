"""Authorization + data-minimisation helpers. Nothing here trusts the LLM."""
import re

# Government / identity numbers: never shown in chat, for any role.
SENSITIVE_FIELDS = {
    "aadhaar_number", "adhaar_no", "pan_no", "FMID_number", "apaar_number",
    "PEN_number", "BPL_number", "SSSMID", "password", "annual_income",
}

_BASE_FIELDS = [
    "first_name", "middle_name", "last_name", "gender", "date_of_birth",
    "blood_group", "roll_number", "scholar_number", "is_active", "email",
]
_FAMILY_FIELDS = ["father_name", "mother_name", "contact_number", "religion", "category"]

PROFILE_FIELDS = {
    "student": _BASE_FIELDS + ["father_name", "mother_name", "contact_number"],
    "guardian": _BASE_FIELDS + _FAMILY_FIELDS,
    "teacher": [f for f in _BASE_FIELDS if f not in ("email", "date_of_birth")],
    "office staff": _BASE_FIELDS + _FAMILY_FIELDS,
    "director": _BASE_FIELDS + _FAMILY_FIELDS,
}


class AccessDenied(Exception):
    """Raised when a user asks for data outside their authorized scope."""


def filter_profile(data: dict, role: str | None) -> dict:
    allowed = PROFILE_FIELDS.get(role or "", [])
    return {k: v for k, v in data.items() if k in allowed and k not in SENSITIVE_FIELDS}


_ID_RE = re.compile(r"[0-9]{1,9}")


def parse_student_id(value) -> int:
    """Strict id parsing: only plain positive integers (or digit strings)."""
    if isinstance(value, bool) or value is None:
        raise AccessDenied("invalid student id")
    s = str(value).strip()
    if not _ID_RE.fullmatch(s) or int(s) <= 0:
        raise AccessDenied("invalid student id")
    return int(s)


# Invisible characters that sneak in when text is copied from a rendered page (zero-width space,
# joiners, BOM, direction marks, soft hyphen).
_INVISIBLE = dict.fromkeys(
    [0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0x2060, 0xFEFF, 0x00AD], None)
_ODD_SPACES = {0x00A0: " ", 0x202F: " ", 0x2007: " ", 0x2009: " "}
# Wrapping characters left over from copying a code-formatted snippet: backtick, quotes, curly quotes.
_WRAP = "`'\"" + chr(0x2018) + chr(0x2019) + chr(0x201C) + chr(0x201D) + " \t\r\n"


def clean_command(text: str) -> str:
    """Normalise a pasted chat command: drop invisible characters, turn odd spaces into normal
    ones and remove the backticks / quotes that come from copying a code-formatted snippet.
    Trailing quote characters are removed ONLY when the text also started with a wrapper, so a
    password that really ends in a quote or backtick is never altered."""
    t = (text or "").translate(_INVISIBLE).translate(_ODD_SPACES).strip()
    lead = len(t) - len(t.lstrip(_WRAP))
    if lead:
        t = t.lstrip(_WRAP).rstrip(_WRAP)
    return t


_LOGIN_RE = re.compile(r"^\s*/login\s+(\S+)\s+(.+?)\s*$", re.IGNORECASE | re.DOTALL)


def parse_login(text: str):
    m = _LOGIN_RE.match(clean_command(text))
    return (m.group(1), m.group(2)) if m else None


def scrub_login(text: str) -> str:
    """Replace the password in a login message before the LLM ever sees history."""
    m = _LOGIN_RE.match(clean_command(text))
    return f"/login {m.group(1)} ***" if m else text


_LONG_ID_RE = re.compile(r"(?<![0-9])[0-9]{12}(?![0-9])")


def mask_sensitive_text(text: str) -> str:
    """Last line of defence: mask any 12-digit number (Aadhaar-like) in replies."""
    return _LONG_ID_RE.sub("XXXXXXXX****", text or "")
