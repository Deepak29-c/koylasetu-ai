"""Normalisation rules (guide section 7.3). Shared by the upload API and the fact extractor."""

import re

_DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")

# "2023-24", "2023–24", "2023/24", "2023-2024", "FY 2023-24", "F.Y. 2023-24"
_FY_RANGE = re.compile(r"^(?:F\.?\s*Y\.?)?\s*(\d{4})\s*[-–—/]\s*(\d{2}|\d{4})$", re.IGNORECASE)
# "FY24", "FY 24", "FY2024" (Indian convention: the year the FY ends in, so FY24 = 2023-24)
_FY_END = re.compile(r"^F\.?\s*Y\.?\s*(\d{2}|\d{4})$", re.IGNORECASE)


def to_ascii_digits(text: str) -> str:
    return text.translate(_DEVANAGARI_DIGITS)


def normalise_fy(value: str | None) -> str | None:
    """Return "FY 2023-24" style, None for blank input. Raises ValueError if unrecognised."""
    if value is None or not value.strip():
        return None
    text = to_ascii_digits(value.strip())

    if m := _FY_RANGE.match(text):
        start, end = int(m.group(1)), m.group(2)
        end_year = int(end) if len(end) == 4 else (start // 100) * 100 + int(end)
        if end_year == start + 1 or (len(end) == 2 and end_year + 100 == start + 1):
            return f"FY {start}-{(start + 1) % 100:02d}"
    elif m := _FY_END.match(text):
        end = int(m.group(1))
        end_year = end if end >= 1000 else 2000 + end
        start = end_year - 1
        return f"FY {start}-{end_year % 100:02d}"

    raise ValueError(f"Financial year not understood: {value!r}. Use a form like FY 2024-25.")
