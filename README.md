# DataRefine

**AI-powered data cleaning tool for messy CSV and Excel files.**

I built DataRefine because real-world datasets are never clean — they come with encoding corruption, unit symbols mixed into numbers, date formats that change halfway through a column, thousands separators that break numeric parsing, and dozens of other issues that take hours to fix manually. DataRefine automates all of that in one click.

---

## How It Works

```
Upload file          AI Analysis            Apply Rules         Export
(.csv/.xls/.xlsx) → (structure + issues) → (14 cleaning ops) → clean .csv + log
      ↓                    ↓                      ↓
 Encoding detected   Rule checklist          Diff preview
 Issues highlighted  Toggle on/off           Amber = changed
```

1. **Upload** — drag and drop any `.csv`, `.xls`, or `.xlsx` file
2. **Raw Preview** — table with amber-highlighted problem cells and column type badges
3. **AI Analysis** — AI reads the first 15 rows, maps column semantics, flags issues, and proposes a transformation rule set
4. **Toggle** — enable or disable individual rules before applying
5. **Apply** — all cleaning runs server-side; only the 15-row sample is sent for analysis
6. **Export** — download the clean CSV and a full Markdown transformation log

---

## What Gets Cleaned

| Issue | Raw | Clean |
|---|---|---|
| Mojibake encoding | `BeyoncÃ©` | `Beyoncé` |
| HTML entities | `AT&amp;T` | `AT&T` |
| Smart / curly quotes | `"Hello"` | `"Hello"` |
| Comma thousands | `780,000,000` | `780000000` |
| Space thousands | `1 500` | `1500` |
| Inline footnotes | `1[4]`, `229,100,000[b]` | `1`, `229100000` |
| Unit symbols | `$12.5`, `2kg`, `€20`, `£30` | `12.5`, `2`, `20`, `30` |
| Superscript digits | `8²` | `82` |
| Comma decimals | `1,5` | `1.5` |
| Date formats | `2024-05-01`, `01/05/2024` | `01.05.24` |
| Empty patterns | `nan`, `N/A`, `None`, `--` | *(blank)* |
| Duplicate rows | exact matches | *(removed)* |
| Column headers | `First Name` | `first_name` |
| Unicode junk | `□`, `▪`, NBSP, control chars | *(stripped)* |

---

## Tech Stack

- **Python 3.10+** · **Streamlit** — interactive web UI, no frontend build step
- **pandas** — vectorized cleaning, type inference, duplicate detection
- **charset-normalizer** — automatic file encoding detection (UTF-8, cp1252, Latin-1, UTF-16)
- **openpyxl / xlrd** — Excel file parsing

---

## Getting Started

```bash
# 1. Clone the repo
git clone https://github.com/RahilDobariya/DataRefine-.git
cd DataRefine-

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run
streamlit run app.py
```

Open `http://localhost:8501` in your browser.

> AI analysis requires an API key — paste it in the sidebar.
> The app works fully without a key using heuristic rules.

---

## Project Structure

```
DataRefine/
├── app.py                    # Streamlit app — 6 UI sections
├── utils/
│   ├── file_parser.py        # Encoding + separator detection, CSV/Excel parsing
│   ├── type_inference.py     # Column type inference, issue detection per cell
│   ├── data_cleaner.py       # 14 cleaning rules, vectorized per-column processing
│   └── ai_client.py          # AI API — structure analysis and rule generation
├── examples/
│   ├── messy_sample.csv      # Raw test file with 8 types of data issues
│   └── clean_sample.csv      # Expected output after cleaning
├── .streamlit/
│   └── config.toml           # Dark theme configuration
└── requirements.txt
```

---

## Cleaning Rules

| Rule | Scope | What it fixes |
|---|---|---|
| `fix_mojibake` | global | Latin-1 misread UTF-8 — `BeyoncÃ©` → `Beyoncé` |
| `decode_html_entities` | per-column | `&amp;` `&nbsp;` `&#160;` → proper characters |
| `normalize_quotes` | per-column | Curly quotes `"` `"` `'` `'` → straight ASCII |
| `strip_footnotes` | per-column | `1[4]` `text[a]` → `1` `text` |
| `remove_comma_thousands` | per-column | `780,000,000` → `780000000` |
| `remove_thousands_sep` | per-column | `1 000` (space/NBSP separator) → `1000` |
| `strip_units` | per-column | `$12.5` `2kg` `€20` → `12.5` `2` `20` |
| `fix_superscripts` | per-column | `8²` `m³` → `82` `m3` |
| `normalize_decimal` | per-column | `1,5` → `1.5` (1–2 decimal places only) |
| `normalize_date` | per-column | `2024-05-01` / `01/05/2024` → `01.05.24` |
| `standardize_empty` | global | `nan` `N/A` `None` `--` → blank |
| `clean_headers` | global | `First Name` → `first_name` |
| `remove_duplicates` | global | Exact row matches removed |
| `collapse_spaces` | global | Trim and collapse whitespace |

---

## Sample Data

The `examples/` folder contains a ready-to-use test pair:

- `messy_sample.csv` — raw file with unit symbols, date format inconsistencies, empty value patterns, duplicate rows, and superscript digits
- `clean_sample.csv` — the expected output after applying all default rules

---

## Author

Rahil Dobariya
