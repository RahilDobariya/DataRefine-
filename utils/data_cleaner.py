import html as _html
import re
import pandas as pd
from typing import Callable

# Superscript digits — explicit Unicode codepoints, no invisible chars
# ⁰=U+2070  ¹=U+00B9  ²=U+00B2  ³=U+00B3  ⁴-⁹=U+2074-U+2079
_SUP_CHARS = (
    "⁰¹²³"
    "⁴⁵⁶⁷⁸⁹"
)
_NRM_CHARS = "0123456789"
_SUP_TABLE = str.maketrans(_SUP_CHARS, _NRM_CHARS)

NBSP = " "  # non-breaking space U+00A0

EMPTY_STRINGS = {
    "nan", "NaN", "none", "None", "NULL", "null",
    "N/A", "n/a", "na", "NA", "-", "--", "#N/A", "#n/a",
}

_BOX_CHARS = re.compile(r"[□▪▫�]")

# Thousands separator: groups of 3 digits separated by space or NBSP
_THOU_RE = re.compile(r"^\d{1,3}([  ]\d{3})+$")

# Superscript digit pattern for detection
_SUP_RE = re.compile(
    r"[⁰¹²³⁴⁵⁶⁷⁸⁹]"
)

# Unit suffixes for detection
_UNIT_RE = re.compile(r"[Ø²°$€£¥%]|\b(kg|cm|lb|oz|ft)\s*$", re.IGNORECASE)

# Inline footnote references like [1], [a], [b], [21]
_FOOTNOTE_RE = re.compile(r"\[\w+\]")

# Comma-as-thousands-separator: 780,000,000 / 10,353,571
_COMMA_THOU_RE = re.compile(r"^\d{1,3}(?:,\d{3})+$")

# Any character in the Latin-1 supplement range — triggers mojibake check
_HIGH_LATIN_RE = re.compile(r"[\x80-\xff]")

# HTML entities: &amp; &nbsp; &#160; &#x00A0;
_HTML_ENT_RE = re.compile(r"&(?:#\d+|#x[0-9a-fA-F]+|[a-zA-Z]\w*);")

# Smart / curly quotes -- keys use escaped codepoints
_SMART_QUOTE_TABLE = str.maketrans({
    "‘": "'",   # left single
    "’": "'",   # right single
    "“": '"',   # left double
    "”": '"',   # right double
    "«": '"',   # left angle
    "»": '"',   # right angle
    "…": "...", # ellipsis
    "­": "",   # soft hyphen
})
_SMART_QUOTE_RE = re.compile("[‘’“”«»…­]")


def _fix_mojibake(s: str) -> str:
    """Re-decode a string that was UTF-8 bytes misread as Latin-1."""
    if not _HIGH_LATIN_RE.search(s):
        return s
    try:
        return s.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def _normalize_date(s: str) -> str | None:
    """Normalize a date string to DD.MM.YY. Returns None if format is ambiguous."""
    # YYYY-MM-DD  or  YYYY/MM/DD
    m = re.match(r"^(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})$", s)
    if m:
        return f"{m.group(3).zfill(2)}.{m.group(2).zfill(2)}.{m.group(1)[2:]}"

    # DD/MM/YYYY  or  MM/DD/YYYY  (2-digit or 4-digit year)
    m = re.match(r"^(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{2,4})$", s)
    if m:
        a, b, c = m.group(1), m.group(2), m.group(3)
        yr = c[2:] if len(c) == 4 else c
        if int(a) > 12:                              # a must be day
            return f"{a.zfill(2)}.{b.zfill(2)}.{yr}"
        if int(b) > 12:                              # b must be day, a=month
            return f"{b.zfill(2)}.{a.zfill(2)}.{yr}"
        return None                                  # ambiguous — leave as-is

    return None


def clean_cell(value, flags: dict) -> tuple[str, bool]:
    """
    Apply cleaning flags to a single cell value.
    Returns (cleaned_value, changed: bool).
    """
    val = "" if value is None else str(value)
    original = val

    if flags.get("fix_mojibake"):
        val = _fix_mojibake(val)

    if flags.get("decode_html_entities"):
        if _HTML_ENT_RE.search(val):
            val = _html.unescape(val)

    if flags.get("normalize_quotes"):
        val = val.translate(_SMART_QUOTE_TABLE)

    if flags.get("strip_unicode", True):
        val = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", val)   # C0/C1 control chars
        val = val.replace(NBSP, " ")                       # NBSP → regular space
        val = _BOX_CHARS.sub("", val)                      # box / replacement glyphs

    if flags.get("fix_superscripts"):
        val = val.translate(_SUP_TABLE)

    if flags.get("collapse_spaces", True):
        val = val.strip()
        val = re.sub(r"[ \t]+", " ", val)

    if flags.get("strip_footnotes"):
        val = _FOOTNOTE_RE.sub("", val).strip()

    if flags.get("standardize_empty"):
        if val.strip() in EMPTY_STRINGS:
            val = ""

    if not val:
        return "", original != ""

    if flags.get("remove_thousands_sep"):
        if _THOU_RE.match(val):
            val = re.sub(r"[  ]", "", val)

    if flags.get("remove_comma_thousands"):
        if _COMMA_THOU_RE.match(val):
            val = val.replace(",", "")

    if flags.get("strip_units"):
        val = re.sub(r"^[Ø$€£¥#@~]+", "", val)
        val = re.sub(
            r"\s*\b(kg|g|mg|lb|oz|cm|mm|km|ft|in|ml|l|°C|°F|°|%"
            r"|²|³)\s*$",
            "", val, flags=re.IGNORECASE,
        )
        val = val.strip()

    if flags.get("normalize_decimal"):
        if re.match(r"^-?\d+,\d{1,2}$", val):
            val = val.replace(",", ".")

    if flags.get("normalize_date"):
        normalized = _normalize_date(val)
        if normalized is not None:
            val = normalized

    return val, val != original


def clean_headers(headers: list[str]) -> list[str]:
    """Lowercase, strip special chars, spaces → underscores, deduplicate."""
    cleaned = []
    for h in headers:
        s = str(h or "").strip()
        s = s.replace(NBSP, " ")
        s = re.sub(r"[^\w\s]", "", s)
        s = s.strip().lower()
        s = re.sub(r"\s+", "_", s)
        cleaned.append(s or "column")

    seen: dict[str, int] = {}
    result = []
    for h in cleaned:
        n = seen.get(h, 0)
        seen[h] = n + 1
        result.append(h if n == 0 else f"{h}_{n + 1}")
    return result


def _find_duplicates(df: pd.DataFrame) -> pd.Series:
    key = df.apply(lambda r: "|".join(r.astype(str).str.strip().str.lower()), axis=1)
    return key.duplicated(keep="first")


def apply_cleaning_rules(
    df: pd.DataFrame,
    rules: list[dict],
    on_progress: Callable[[int], None] | None = None,
) -> dict:
    """
    Apply a list of rules to the DataFrame.
    Returns { df, changes, log, total_changed, removed_dupes }
    """
    log: list[dict] = []
    enabled = [r for r in rules if r.get("enabled")]

    global_types = {r["type"] for r in enabled if not r.get("column")}
    col_rules: dict[str, list[str]] = {}
    for r in enabled:
        if r.get("column"):
            col_rules.setdefault(r["column"], []).append(r["type"])

    work = df.copy()

    # ── Step 1: Clean headers ────────────────────────────────────────────────
    if "clean_headers" in global_types:
        new_cols = clean_headers(list(work.columns))
        rename_map = dict(zip(work.columns, new_cols))
        work.rename(columns=rename_map, inplace=True)
        # Remap col_rules to the new column names
        col_rules = {rename_map.get(k, k): v for k, v in col_rules.items()}
        log.append({"col": "(headers)", "msg": "Cleaned column headers",
                    "count": len(new_cols), "level": "success"})

    # ── Step 2: Remove duplicates ────────────────────────────────────────────
    removed_dupes = 0
    if "remove_duplicates" in global_types:
        mask = _find_duplicates(work)
        removed_dupes = int(mask.sum())
        if removed_dupes:
            work = work[~mask].reset_index(drop=True)
            log.append({"col": "(global)", "msg": "Removed duplicate rows",
                        "count": removed_dupes, "level": "warning"})

    # ── Step 3: Clean cells — vectorized per column ──────────────────────────
    changes: dict[tuple, bool] = {}
    col_change_counts: dict[str, int] = {}
    total_cols = len(work.columns)

    for c_pos, col in enumerate(work.columns):
        applicable = set(col_rules.get(col, []) + list(global_types))

        flags = {
            "strip_unicode":          True,
            "collapse_spaces":        True,
            "fix_mojibake":           "fix_mojibake"           in applicable,
            "decode_html_entities":   "decode_html_entities"   in applicable,
            "normalize_quotes":       "normalize_quotes"        in applicable,
            "strip_footnotes":        "strip_footnotes"         in applicable,
            "standardize_empty":      "standardize_empty"       in applicable,
            "strip_units":            "strip_units"             in applicable,
            "fix_superscripts":       "fix_superscripts"        in applicable,
            "normalize_decimal":      "normalize_decimal"       in applicable,
            "normalize_date":         "normalize_date"          in applicable,
            "remove_thousands_sep":   "remove_thousands_sep"    in applicable,
            "remove_comma_thousands": "remove_comma_thousands"  in applicable,
        }

        # Skip column entirely if no rules apply beyond strip_unicode/collapse
        has_real_rules = any(flags[k] for k in flags if k not in (
            "strip_unicode", "collapse_spaces"))
        needs_basic = True  # always run strip_unicode + collapse

        original_col = work[col].astype(str)

        # Apply clean_cell to every cell in the column
        cleaned_col = original_col.apply(lambda v: clean_cell(v, flags)[0])

        # Find which rows actually changed
        changed_mask = cleaned_col != original_col
        if changed_mask.any():
            work[col] = cleaned_col
            changed_rows = work.index[changed_mask].tolist()
            for row_label in changed_rows:
                changes[(row_label, col)] = True
            col_change_counts[col] = int(changed_mask.sum())

        # Progress by column (fast enough for most files)
        on_progress and on_progress(int((c_pos + 1) / total_cols * 100))

    for col, count in col_change_counts.items():
        log.append({"col": col, "msg": "cells cleaned", "count": count, "level": "success"})

    return {
        "df":            work,
        "changes":       changes,
        "log":           log,
        "total_changed": len(changes),
        "removed_dupes": removed_dupes,
    }


def build_default_rules(df: pd.DataFrame) -> list[dict]:
    """Heuristic rule set built from raw DataFrame — used without AI analysis."""
    rules = [
        {"id": "r_headers", "label": "Clean column headers (lowercase + underscores)",       "column": None, "type": "clean_headers",    "enabled": True},
        {"id": "r_empty",   "label": "Standardize empty values (nan, N/A, -- → blank)",      "column": None, "type": "standardize_empty", "enabled": True},
        {"id": "r_unicode", "label": "Remove control characters and box glyphs",              "column": None, "type": "strip_unicode",     "enabled": True},
        {"id": "r_spaces",  "label": "Collapse extra whitespace in all cells",                "column": None, "type": "collapse_spaces",   "enabled": True},
        {"id": "r_dupes",   "label": "Remove exact duplicate rows",                          "column": None, "type": "remove_duplicates", "enabled": True},
    ]

    sample = df.head(200)
    date_re = re.compile(r"^\d{1,2}[.\-/]\d{1,2}[.\-/](\d{2}|\d{4})$")
    fn_attached_re = re.compile(r"\w\[\w+\]")

    # Global: mojibake detection (scan all columns, add one rule if any found)
    mojibake_total = 0
    for col in df.columns:
        vals = [str(v) for v in sample[col].tolist() if str(v).strip()]
        mojibake_total += sum(
            1 for v in vals
            if _HIGH_LATIN_RE.search(v) and _fix_mojibake(v) != v
        )
    if mojibake_total > 0:
        rules.append({
            "id": "r_mojibake", "label": f"Fix character encoding errors (mojibake) — {mojibake_total} cells detected",
            "column": None, "type": "fix_mojibake", "enabled": True,
        })

    for col in df.columns:
        vals = [str(v) for v in sample[col].tolist() if str(v).strip()]
        if not vals:
            continue

        date_hits = sum(1 for v in vals if date_re.match(v.strip()))
        if date_hits / len(vals) > 0.5:
            rules.append({
                "id": f"r_date_{col}", "column": col, "type": "normalize_date", "enabled": True,
                "label": f'Normalize dates in "{col}" to DD.MM.YY',
            })

        unit_hits = sum(1 for v in vals
                        if re.search(r"[Ø²°$€£¥%]|(kg|cm|lb|oz)\s*$",
                                     v, re.IGNORECASE))
        if unit_hits > 0:
            rules.append({
                "id": f"r_units_{col}", "column": col, "type": "strip_units", "enabled": True,
                "label": f'Strip unit symbols from "{col}" ({unit_hits} cells)',
            })

        dec_hits = sum(1 for v in vals if re.match(r"^-?\d+,\d{1,2}$", v.strip()))
        if dec_hits > 0:
            rules.append({
                "id": f"r_dec_{col}", "column": col, "type": "normalize_decimal", "enabled": True,
                "label": f'Fix comma decimals in "{col}" e.g. 1,5 -> 1.5 ({dec_hits} cells)',
            })

        html_hits = sum(1 for v in vals if _HTML_ENT_RE.search(v))
        if html_hits > 0:
            rules.append({
                "id": f"r_html_{col}", "column": col, "type": "decode_html_entities", "enabled": True,
                "label": f'Decode HTML entities in "{col}" e.g. &amp; -> & ({html_hits} cells)',
            })

        quote_hits = sum(1 for v in vals if _SMART_QUOTE_RE.search(v))
        if quote_hits > 0:
            rules.append({
                "id": f"r_quotes_{col}", "column": col, "type": "normalize_quotes", "enabled": True,
                "label": f'Replace smart/curly quotes in "{col}" ({quote_hits} cells)',
            })

        sup_hits = sum(1 for v in vals if _SUP_RE.search(v))
        if sup_hits > 0:
            rules.append({
                "id": f"r_sup_{col}", "column": col, "type": "fix_superscripts", "enabled": True,
                "label": f'Replace superscript digits in "{col}" ({sup_hits} cells)',
            })

        fn_hits = sum(1 for v in vals if fn_attached_re.search(v))
        if fn_hits > 0:
            rules.append({
                "id": f"r_fn_{col}", "column": col, "type": "strip_footnotes", "enabled": True,
                "label": f'Strip inline footnotes from "{col}" e.g. 1[4] -> 1 ({fn_hits} cells)',
            })

        cthou_hits = sum(1 for v in vals if _COMMA_THOU_RE.match(v.strip()))
        if cthou_hits > 0:
            rules.append({
                "id": f"r_cthou_{col}", "column": col, "type": "remove_comma_thousands", "enabled": True,
                "label": f'Remove comma thousands in "{col}" e.g. 780,000,000 -> 780000000 ({cthou_hits} cells)',
            })

    return rules
