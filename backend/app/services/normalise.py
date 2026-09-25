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


def fy_start_year(fy: str) -> int:
    """ "FY 2024-25" -> 2024."""
    return int(fy[3:7])


# --- Numbers ---------------------------------------------------------------------------------

_EMPTY = {"", "-", "–", "—", "na", "n.a.", "n/a", "nil", "..", "…"}
_PLAIN_NUMBER = re.compile(r"^\(?-?\d[\d,]*(?:\.\d+)?\)?$")


def parse_number(raw: str) -> float | None:
    """Cell text -> number. Indian (4,00,715.45) and western (400,715.45) grouping, Hindi
    digits. None for empty markers ("-", "NA") and anything that isn't a plain number, so
    arrows, % signs or words never become figures by accident."""
    text = to_ascii_digits(raw).strip().replace(" ", "")
    if text.lower() in _EMPTY or not _PLAIN_NUMBER.match(text):
        return None
    negative = text.startswith("(") and text.endswith(")")  # accounting style (12.5)
    value = float(text.strip("()").replace(",", ""))
    return -value if negative else value


# --- Units (standard: MT = million tonnes; Mcum for overburden) --------------------------------

# (pattern, standard unit, factor to convert to it). Order matters: most specific first.
_UNITS = [
    (re.compile(r"lakh\s*(?:tonnes?|te|t)\b|\blt\b", re.I), "MT", 0.1),
    (
        re.compile(r"thousand\s*(?:tonnes?|te|t)\b|\b(?:'000|000)\s*(?:tonnes?|te|t)\b", re.I),
        "MT",
        0.001,
    ),
    (
        re.compile(
            r"million\s*(?:tonnes?|tonne|te|t)\b|mill\.?\s*te\b|\bM\.?T\.?(?![a-z])|\bMt\b", re.I
        ),
        "MT",
        1.0,
    ),
    (re.compile(r"billion\s*(?:tonnes?|tonne|te|t)\b|\bBT\b", re.I), "MT", 1000.0),
    (
        re.compile(r"million\s*cu(?:bic)?\.?\s*m(?:etres?)?\b|\bM\.?\s?Cum\b|\bMm3\b", re.I),
        "Mcum",
        1.0,
    ),
]


def find_unit(text: str) -> tuple[str, str, float] | None:
    """First unit mentioned in `text` -> (unit as written, standard unit, factor)."""
    best = None
    for pattern, std, factor in _UNITS:
        m = pattern.search(text)
        if m and (best is None or m.start() < best[0]):
            best = (m.start(), m.group(0).strip(), std, factor)
    return best[1:] if best else None


# --- Names -------------------------------------------------------------------------------------

# Subsidiary alias map (guide 7.3). Keys are matched on a normalised form (letters only, upper).
SUBSIDIARY_ALIASES = {
    "ECL": ["ECL", "EASTERNCOALFIELDS"],
    "BCCL": ["BCCL", "BHARATCOKINGCOAL"],
    "CCL": ["CCL", "CENTRALCOALFIELDS"],
    "NCL": ["NCL", "NORTHERNCOALFIELDS"],
    "WCL": ["WCL", "WESTERNCOALFIELDS"],
    "SECL": ["SECL", "SOUTHEASTERNCOALFIELDS"],
    "MCL": ["MCL", "MAHANADICOALFIELDS"],
    "NEC": ["NEC", "NORTHEASTERNCOALFIELDS"],
    "CIL": ["CIL", "COALINDIA", "COALINDIALIMITED", "CILTOTAL", "TOTALCIL"],
    "SCCL": ["SCCL", "SINGARENICOLLIERIES", "SINGARENI"],
    "CAPTIVE": ["CAPTIVES", "CAPTIVE", "CAPTIVESOTHERS", "CAPTIVEOTHERS", "CAPTIVECOMMERCIAL"],
    "ALL_INDIA": ["GRANDTOTAL", "ALLINDIA", "ALLINDIATOTAL", "INDIA", "TOTALINDIA"],
}
CIL_SUBSIDIARIES = ["ECL", "BCCL", "CCL", "NCL", "WCL", "SECL", "MCL", "NEC"]

COAL_STATES = [
    "ANDHRA PRADESH", "ARUNACHAL PRADESH", "ASSAM", "BIHAR", "CHHATTISGARH", "JHARKHAND",
    "MADHYA PRADESH", "MAHARASHTRA", "MEGHALAYA", "NAGALAND", "ODISHA", "SIKKIM", "TELANGANA",
    "UTTAR PRADESH", "WEST BENGAL", "TAMIL NADU", "RAJASTHAN", "GUJARAT", "KERALA",
    "JAMMU & KASHMIR", "PUDUCHERRY",
]  # fmt: skip
_STATE_KEYS = {re.sub(r"[^A-Z]", "", s): s for s in COAL_STATES} | {"ORISSA": "ODISHA"}

_LETTERS = re.compile(r"[^A-Z]")
_ALIAS_INDEX = {alias: code for code, aliases in SUBSIDIARY_ALIASES.items() for alias in aliases}


def _key(text: str) -> str:
    # "10 Captives/Others" -> "CAPTIVESOTHERS", "M.C.L." -> "MCL"
    return _LETTERS.sub("", text.upper().replace("LIMITED", "").replace("LTD", ""))


def subsidiary_code(text: str) -> str | None:
    return _ALIAS_INDEX.get(_key(text)) if text and text.strip() else None


def state_name(text: str) -> str | None:
    return _STATE_KEYS.get(_key(text)) if text and text.strip() else None


# --- Months ------------------------------------------------------------------------------------

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1
)}  # fmt: skip


def month_in_fy(month: int, fy: str) -> str:
    """Month number within an Indian FY (April-March) -> "YYYY-MM"."""
    start = fy_start_year(fy)
    return f"{start if month >= 4 else start + 1}-{month:02d}"
