import json
import re
import anthropic
import pandas as pd

_MODEL = "claude-sonnet-4-20250514"

_SYSTEM_PROMPT = (
    "You are a data quality analyst. Analyze raw tabular data and return structured "
    "JSON only. No markdown fences, no explanation — pure valid JSON."
)


def analyze_structure(api_key: str, df: pd.DataFrame) -> dict:
    """
    Structure analysis — sends first 15 rows and returns a structured dict:
      row_format, skip_rows, column_map, issues, rules
    """
    client = anthropic.Anthropic(api_key=api_key)

    sample = df.head(15)
    rows_json = json.dumps(
        [sample.columns.tolist()] + sample.values.tolist(),
        default=str,
        ensure_ascii=False,
    )

    prompt = f"""Analyze this raw tabular data (headers + first {len(sample)} rows) and return JSON only.

DATA:
{rows_json}

Return this exact JSON shape:
{{
  "row_format": "single" | "paired" | "multi-header",
  "skip_rows": 0,
  "column_map": [
    {{ "index": 0, "raw_name": "...", "semantic": "...", "type": "date|integer|float|text|boolean|list|mixed" }}
  ],
  "issues": [
    {{ "column": "...", "type": "...", "example": "...", "severity": "low|medium|high" }}
  ],
  "rules": [
    {{ "id": "r1", "label": "...", "column": "..." or null, "type": "normalize_date|strip_units|fix_superscripts|normalize_decimal|standardize_empty|clean_headers|remove_duplicates|collapse_spaces|remove_thousands_sep|remove_comma_thousands|strip_footnotes|fix_mojibake|decode_html_entities|normalize_quotes", "enabled": true }}
  ]
}}

Check for: unit_symbol, comma_decimal, superscript_digit, mixed_date_format, empty_value_pattern, unicode_control, duplicate_rows, thousands_separator, comma_thousands_separator, inline_footnote_references, mojibake_encoding, html_entities, smart_quotes.
Generate one rule per detected issue type per column. Always include global rules: clean_headers, standardize_empty, remove_duplicates.
- fix_mojibake (global): text fields with Ã©, â€, Â£ style Latin-1 misread UTF-8.
- strip_footnotes (per-column): numeric/text cells with [1], [a] style Wikipedia markers.
- remove_comma_thousands (per-column): number fields using commas as thousands separators e.g. 780,000,000.
- decode_html_entities (per-column): cells with &amp; &nbsp; &#160; and similar HTML escapes.
- normalize_quotes (per-column): cells containing curly/smart quotes.
"""

    response = client.messages.create(
        model=_MODEL,
        max_tokens=4096,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            return json.loads(match.group(0))
        raise ValueError("AI returned a non-JSON response. Try again.")


def classify_row_intent(api_key: str, context_rows: list, target_index: int) -> dict:
    """
    Row intent classification.
    Returns { "type": "data" | "header" | "note" | "continuation" }
    """
    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""Given these rows (JSON array of arrays), classify row at index {target_index}.

ROWS:
{json.dumps(context_rows, default=str)}

Return JSON only:
{{ "type": "data" | "header" | "note" | "continuation" }}"""

    response = client.messages.create(
        model=_MODEL,
        max_tokens=64,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    return json.loads(response.content[0].text.strip())
