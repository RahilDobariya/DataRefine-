import re
import pandas as pd

DATE_PATTERNS = [
    re.compile(r"^\d{1,2}[.\-/]\d{1,2}[.\-/](\d{2}|\d{4})$"),  # DD.MM.YYYY or MM/DD/YY
    re.compile(r"^\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2}$"),            # YYYY-MM-DD
    re.compile(r"^\d{1,2}\s+\w{3}\s+\d{4}$"),                    # 12 Jan 2023
]

EMPTY_VALS = {"", "nan", "none", "n/a", "na", "null", "-", "--", "#n/a"}
BOOL_VALS  = {"true", "false", "yes", "no", "1", "0", "y", "n"}

NBSP = " "  # non-breaking space U+00A0

# Superscript digit codepoints:
# ⁰=U+2070  ¹=U+00B9  ²=U+00B2  ³=U+00B3  ⁴-⁹=U+2074-U+2079
_SUP_RE     = re.compile(r"[⁰¹²³⁴⁵⁶⁷⁸⁹]")
_UNIT_RE    = re.compile(r"[Ø²°$€£¥%]|\b(kg|cm|lb|oz|ft)\s*$", re.IGNORECASE)
_COM_DEC_RE = re.compile(r"^\d+,\d{1,2}$")
_THOU_RE    = re.compile(r"\d[  ]\d{3}")   # space or NBSP as thousands sep
_EMPTY_PAT  = re.compile(r"^(nan|NaN|None|N/A|n/a|null|--|-)$")
_BOX_RE     = re.compile(r"[□▪▫�]")

# Mojibake: Latin-1 re-interpretation of 2-byte UTF-8 (Ã© → é, â€ → —, etc.)
_MOJIBAKE_RE      = re.compile(r"Ã[\x80-\xff]|Â[\x80-\xff]|â[\x80-\xff]")
# Footnote reference glued to a value: 1[4], 229,100,000[b], Tour[21]
_FN_ATTACHED_RE   = re.compile(r"\w\[\w+\]")
# Comma as thousands separator: 780,000,000 / 10,353,571
_COMMA_THOU_RE_TI = re.compile(r"^\d{1,3}(?:,\d{3})+$")
# HTML entities: &amp; &nbsp; &#160;
_HTML_ENT_RE_TI   = re.compile(r"&(?:#\d+|#x[0-9a-fA-F]+|[a-zA-Z]\w*);")
# Smart / curly quotes and soft hyphen
_SMART_QUOTE_RE   = re.compile("[‘’“”«»…­]")


def infer_column_type(values: list) -> dict:
    """
    Infer dominant type for a column of string values.
    Returns { 'type': str, 'confidence': float }.
    """
    non_empty = [
        str(v).strip()
        for v in values
        if str(v).strip().lower() not in EMPTY_VALS
    ]

    if not non_empty:
        return {"type": "empty", "confidence": 1.0}

    n = len(non_empty)
    date_c = int_c = float_c = bool_c = list_c = 0

    for v in non_empty:
        if any(p.match(v) for p in DATE_PATTERNS):
            date_c += 1
            continue
        try:
            int(v.replace(",", "").replace(" ", ""))
            int_c += 1
            continue
        except ValueError:
            pass
        try:
            float(v.replace(",", "."))
            float_c += 1
            continue
        except ValueError:
            pass
        if v.lower() in BOOL_VALS:
            bool_c += 1
            continue
        parts = v.split(",")
        if len(parts) >= 2 and all(p.strip() for p in parts):
            list_c += 1

    if date_c / n > 0.7:
        return {"type": "date",    "confidence": round(date_c / n, 2)}
    if int_c / n > 0.8:
        return {"type": "integer", "confidence": round(int_c / n, 2)}
    if (int_c + float_c) / n > 0.8:
        return {"type": "float",   "confidence": round((int_c + float_c) / n, 2)}
    if bool_c / n > 0.8:
        return {"type": "boolean", "confidence": round(bool_c / n, 2)}
    if list_c / n > 0.4:
        return {"type": "list",    "confidence": round(list_c / n, 2)}
    return {"type": "text", "confidence": 1.0}


def infer_all_column_types(df: pd.DataFrame) -> dict:
    """Returns { col_name: { type, confidence } } for every column."""
    return {col: infer_column_type(df[col].tolist()) for col in df.columns}


def is_problematic(value) -> bool:
    """
    True if a cell value looks like it needs cleaning.
    Used to highlight amber cells in the raw data preview.
    """
    s = str(value if value is not None else "").strip()
    if not s:
        return False
    if _EMPTY_PAT.match(s):        return True   # nan / N/A / -- etc.
    if _UNIT_RE.search(s):         return True   # unit symbols: $ kg °
    if NBSP in s:                  return True   # non-breaking space
    if _SUP_RE.search(s):          return True   # superscript digits ² ³
    if _COM_DEC_RE.match(s):       return True   # comma decimal: 1,5
    if _THOU_RE.search(s):         return True   # thousands space: 1 000
    if _BOX_RE.search(s):          return True   # box / replacement glyphs
    if _MOJIBAKE_RE.search(s):     return True   # encoding corruption: Ã© â€
    if _FN_ATTACHED_RE.search(s):  return True   # footnote glued to value: 1[4]
    if _COMMA_THOU_RE_TI.match(s): return True   # comma thousands: 780,000,000
    if _HTML_ENT_RE_TI.search(s):  return True   # HTML entity: &amp; &nbsp;
    if _SMART_QUOTE_RE.search(s):  return True   # curly/smart quotes: " " ' '
    return False
