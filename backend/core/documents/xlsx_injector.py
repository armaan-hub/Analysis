"""
xlsx/csv full injection for small files.

Parses xlsx, xls, and csv files under 100KB into structured row-by-row text
so the LLM can reason over exact cell values without relying solely on
chunked embeddings.
"""

import logging
import os
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

_MAX_SIZE = 100 * 1024  # 100 KB
_SUPPORTED_EXTENSIONS = {".xlsx", ".xls", ".csv"}
_HEADER_REPEAT_INTERVAL = 20


def should_inject(file_path: str, file_size: int = 0) -> bool:
    """Return True if the file is a small xlsx/xls/csv suitable for full injection."""
    ext = Path(file_path).suffix.lower()
    if ext not in _SUPPORTED_EXTENSIONS:
        return False
    # Use provided size or fall back to filesystem stat
    size = file_size if file_size > 0 else os.path.getsize(file_path)
    return size < _MAX_SIZE


def _sheet_to_text(df: pd.DataFrame, sheet_name: str) -> str:
    """Convert a single DataFrame (sheet) to structured row-by-row text."""
    if df.empty:
        return ""

    # Clean column names
    headers = [str(c).strip() for c in df.columns]
    header_line = f"--- Headers: {', '.join(headers)} ---"

    lines = [f"Sheet: {sheet_name}"]
    for idx, row in df.iterrows():
        row_num = idx + 1 if isinstance(idx, int) else idx
        pairs = ", ".join(
            f"{h}={v}" for h, v in zip(headers, row.values)
        )
        lines.append(f"Row {row_num}: {pairs}")
        # Repeat headers every N rows for LLM readability
        if isinstance(row_num, int) and row_num % _HEADER_REPEAT_INTERVAL == 0:
            lines.append(header_line)

    # Always include headers at the end if not just added
    if len(lines) > 1 and not lines[-1].startswith("--- Headers"):
        lines.append(header_line)

    return "\n".join(lines)


def parse_to_structured_text(file_path: str) -> str:
    """Parse an xlsx/xls/csv file into structured row-by-row text."""
    ext = Path(file_path).suffix.lower()
    sections: list[str] = []

    try:
        if ext == ".csv":
            df = pd.read_csv(file_path)
            text = _sheet_to_text(df, "Main")
            if text:
                sections.append(text)
        else:
            xls = pd.ExcelFile(file_path)
            for sheet_name in xls.sheet_names:
                df = pd.read_excel(xls, sheet_name=sheet_name)
                text = _sheet_to_text(df, sheet_name)
                if text:
                    sections.append(text)
    except Exception as e:
        logger.warning(f"Failed to parse {file_path}: {e}")
        return ""

    return "\n\n".join(sections)
