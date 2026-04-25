import io
import pandas as pd


def _detect_encoding(raw: bytes) -> str:
    """Detect file encoding via BOM, then charset_normalizer, then fallback."""
    # BOM detection — fastest and most reliable
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return "utf-16"

    # charset_normalizer — accurate for ambiguous encodings (Latin-1 vs UTF-8 etc.)
    try:
        from charset_normalizer import from_bytes
        best = from_bytes(
            raw[:32768],  # sample first 32 KB — enough for detection
            cp_isolation=["utf-8", "cp1252", "latin-1", "utf-16", "iso-8859-2"],
        ).best()
        if best:
            return str(best.encoding)
    except Exception:
        pass

    # Fallback: try strict UTF-8, then cp1252 (superset of latin-1)
    try:
        raw.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        return "cp1252"


def _detect_separator(header_line: str) -> str:
    """Count unquoted occurrences of each candidate separator in the header row."""
    candidates = {",": 0, ";": 0, "\t": 0, "|": 0}
    in_quote = False
    for ch in header_line:
        if ch == '"':
            in_quote = not in_quote
        elif not in_quote and ch in candidates:
            candidates[ch] += 1
    best = max(candidates, key=candidates.get)
    return best if candidates[best] > 0 else ","


def parse_file(uploaded_file) -> tuple[pd.DataFrame, dict]:
    """
    Parse an uploaded Streamlit file object (.csv / .xls / .xlsx).

    For CSV files:
      - Auto-detects encoding (handles UTF-8, UTF-8 BOM, cp1252/Latin-1, UTF-16)
      - Auto-detects separator (comma, semicolon, tab, pipe)

    Returns (DataFrame with all columns as strings, file_info dict).
    """
    name = uploaded_file.name
    ext  = name.rsplit(".", 1)[-1].lower()
    size = uploaded_file.size

    if ext == "csv":
        raw      = uploaded_file.read()
        encoding = _detect_encoding(raw)
        text     = raw.decode(encoding, errors="replace")
        header   = text.split("\n")[0] if text else ""
        sep      = _detect_separator(header)

        df = pd.read_csv(
            io.StringIO(text),
            sep=sep,
            dtype=str,
            keep_default_na=False,
        )
        extra = {"encoding": encoding, "separator": sep}

    elif ext in ("xls", "xlsx"):
        engine = "openpyxl" if ext == "xlsx" else "xlrd"
        df = pd.read_excel(
            uploaded_file,
            dtype=str,
            keep_default_na=False,
            engine=engine,
        )
        extra = {"encoding": "binary", "separator": "N/A"}

    else:
        raise ValueError(f"Unsupported file type: .{ext}")

    # Drop fully empty rows/cols, fill remaining NaN with ""
    df = df.dropna(how="all")
    df = df.loc[:, df.replace("", pd.NA).notna().any()]  # drop all-empty columns
    df = df.fillna("")
    df.columns = [str(c).strip() for c in df.columns]

    file_info = {
        "name": name,
        "size": size,
        "rows": len(df),
        "cols": len(df.columns),
        **extra,
    }

    return df, file_info


def format_file_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"
