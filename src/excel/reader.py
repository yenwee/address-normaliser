"""Excel input: read .xls/.xlsx files, extract ADDR columns, detect header rows.

Handles both legacy .xls (via xlrd with corruption tolerance) and modern
.xlsx (via openpyxl). ADDR columns are identified by the ADDR<number>
pattern and sorted numerically, not lexically.
"""

import re
from pathlib import Path

import pandas as pd

from src.config import ADDR_COLUMN_PREFIX, IC_COLUMN

_HEADER_IC_VALUES = frozenset({"ic", "icno"})
_ADDR_COL_RE = re.compile(rf"^{ADDR_COLUMN_PREFIX}(\d+)$", re.IGNORECASE)


def read_excel(path: str) -> pd.DataFrame:
    """Read an Excel file, supporting both .xls and .xlsx formats.

    For .xls files, uses xlrd with ignore_workbook_corruption=True.
    For .xlsx files, uses openpyxl.

    Args:
        path: Path to the Excel file.

    Returns:
        A pandas DataFrame with the file contents.
    """
    ext = Path(path).suffix.lower()

    if ext == ".xls":
        import xlrd

        workbook = xlrd.open_workbook(path, ignore_workbook_corruption=True)
        return pd.read_excel(workbook, engine="xlrd")

    return pd.read_excel(path, engine="openpyxl")


def get_addr_columns(df: pd.DataFrame) -> list[str]:
    """Find and sort ADDR columns by their numeric suffix.

    Args:
        df: DataFrame whose columns to inspect.

    Returns:
        Sorted list of column names matching ADDR<number> pattern.
    """
    addr_cols = []
    for col in df.columns:
        match = _ADDR_COL_RE.match(str(col))
        if match:
            addr_cols.append((int(match.group(1)), str(col)))

    addr_cols.sort(key=lambda pair: pair[0])
    return [col for _, col in addr_cols]


def is_header_row(row: pd.Series) -> bool:
    """Check if a row is a repeated header (ICNO value is a header label)."""
    ic_value = row.get(IC_COLUMN, "")
    if pd.isna(ic_value):
        return False
    return str(ic_value).strip().lower() in _HEADER_IC_VALUES
