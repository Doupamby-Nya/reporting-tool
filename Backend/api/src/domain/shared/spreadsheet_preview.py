"""A read-only picture of a workbook, for showing a regulator's sheet in the page.

A browser cannot render .xls or .xlsx itself, so the reference screens used to
offer these files only as downloads. This reads the workbook once and returns
what a viewer needs to draw it: every sheet's grid of displayed values, its
merged ranges, and the two pieces of formatting that carry meaning on a
regulator's form (bold headings and filled cells). Nothing else is kept — the
file itself is still one click away for anyone who needs the real thing.

Both formats are read: .xlsx with openpyxl, legacy .xls with xlrd.
"""

from __future__ import annotations

import io
from datetime import date, datetime
from typing import Any

#: A viewer is for reading, not for loading a data dump. The regulator's
#: sheets are well inside these bounds; anything larger is cut and says so.
MAX_ROWS = 1000
MAX_COLS = 60


def preview(filename: str, content: bytes) -> dict[str, Any]:
    extension = filename.rsplit(".", 1)[-1].lower()
    if extension in ("xlsx", "xlsm"):
        sheets = _xlsx_sheets(content)
    elif extension == "xls":
        sheets = _xls_sheets(content)
    else:
        raise ValueError(f"'{filename}' is not a spreadsheet this viewer can read.")
    # A regulator's workbook usually opens on a cover page carrying little
    # more than a logo; the viewer opens on the sheet with the most content.
    filled = [sum(1 for row in s["rows"] for cell in row if cell and cell.get("v")) for s in sheets]
    default = filled.index(max(filled)) if filled else 0
    return {"filename": filename, "sheets": sheets, "default_sheet": default}


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, datetime):
        return value.date().isoformat() if value.time() == datetime.min.time() else value.isoformat(sep=" ")
    if isinstance(value, date):
        return value.isoformat()
    return str(value).strip()


def _trim(rows: list[list[dict[str, Any] | None]]) -> tuple[list[list[dict[str, Any] | None]], int]:
    """Drops trailing empty rows and columns, so a sheet formatted down to row
    65 536 does not render as 65 536 blank lines."""
    last_row, last_col = -1, -1
    for r, row in enumerate(rows):
        for c, cell in enumerate(row):
            if cell and (cell.get("v") or cell.get("bg")):
                last_row, last_col = max(last_row, r), max(last_col, c)
    kept = [row[: last_col + 1] for row in rows[: last_row + 1]]
    return kept, last_col + 1


def _sheet(name: str, rows: list[list[dict[str, Any] | None]], merges: list[list[int]],
           total_rows: int, total_cols: int, widths: dict[int, float]) -> dict[str, Any]:
    grid, cols = _trim(rows)
    return {
        "name": name,
        "rows": grid,
        "cols": cols,
        "merges": [m for m in merges if m[0] < len(grid) and m[1] < cols],
        # Column widths in characters, as the workbook sets them; the viewer
        # turns them into pixels so the sheet keeps its designed proportions.
        "widths": [round(widths.get(c, 0), 1) for c in range(cols)],
        "truncated": total_rows > MAX_ROWS or total_cols > MAX_COLS,
    }


# =============================================================================
# .xlsx
# =============================================================================

def _xlsx_colour(fill: Any) -> str | None:
    try:
        if fill is None or fill.fill_type != "solid":
            return None
        colour = fill.fgColor
        if colour.type != "rgb" or not isinstance(colour.rgb, str):
            return None
        rgb = colour.rgb[-6:]
        return None if rgb.upper() in ("FFFFFF", "000000") else f"#{rgb}"
    except Exception:
        return None


def _xlsx_sheets(content: bytes) -> list[dict[str, Any]]:
    from openpyxl import load_workbook
    from openpyxl.utils import column_index_from_string

    book = load_workbook(io.BytesIO(content), data_only=True)
    sheets = []
    for sheet in book.worksheets:
        if sheet.sheet_state != "visible":
            continue
        n_rows, n_cols = min(sheet.max_row, MAX_ROWS), min(sheet.max_column, MAX_COLS)
        rows: list[list[dict[str, Any] | None]] = []
        for row in sheet.iter_rows(min_row=1, max_row=n_rows, max_col=n_cols):
            line: list[dict[str, Any] | None] = []
            for cell in row:
                value, bg = _text(cell.value), _xlsx_colour(cell.fill)
                bold = bool(cell.font and cell.font.bold)
                line.append({"v": value, **({"b": 1} if bold and value else {}),
                             **({"bg": bg} if bg else {})} if value or bg else None)
            rows.append(line)
        merges = [[m.min_row - 1, m.min_col - 1, m.max_row - m.min_row + 1, m.max_col - m.min_col + 1]
                  for m in sheet.merged_cells.ranges]
        widths = {}
        for letter, dimension in sheet.column_dimensions.items():
            if dimension.width:
                widths[column_index_from_string(letter) - 1] = dimension.width
        sheets.append(_sheet(sheet.title, rows, merges, sheet.max_row, sheet.max_column, widths))
    return sheets


# =============================================================================
# .xls
# =============================================================================

def _xls_sheets(content: bytes) -> list[dict[str, Any]]:
    import xlrd

    try:
        book = xlrd.open_workbook(file_contents=content, formatting_info=True)
        formatted = True
    except Exception:
        # Some generators write BIFF that xlrd reads only without formatting.
        book = xlrd.open_workbook(file_contents=content)
        formatted = False

    sheets = []
    for sheet in book.sheets():
        if getattr(sheet, "visibility", 0) != 0:
            continue
        n_rows, n_cols = min(sheet.nrows, MAX_ROWS), min(sheet.ncols, MAX_COLS)
        rows: list[list[dict[str, Any] | None]] = []
        for r in range(n_rows):
            line: list[dict[str, Any] | None] = []
            for c in range(n_cols):
                cell = sheet.cell(r, c)
                if cell.ctype == xlrd.XL_CELL_DATE:
                    try:
                        value = _text(xlrd.xldate.xldate_as_datetime(cell.value, book.datemode))
                    except Exception:
                        value = _text(cell.value)
                elif cell.ctype == xlrd.XL_CELL_BOOLEAN:
                    value = _text(bool(cell.value))
                elif cell.ctype == xlrd.XL_CELL_ERROR:
                    value = ""
                else:
                    value = _text(cell.value)
                bold, bg = False, None
                if formatted:
                    try:
                        xf = book.xf_list[cell.xf_index]
                        bold = book.font_list[xf.font_index].bold
                        if xf.background.fill_pattern == 1:
                            rgb = book.colour_map.get(xf.background.pattern_colour_index)
                            if rgb and rgb not in ((255, 255, 255), (0, 0, 0)):
                                bg = "#%02X%02X%02X" % rgb
                    except Exception:
                        pass
                line.append({"v": value, **({"b": 1} if bold and value else {}),
                             **({"bg": bg} if bg else {})} if value or bg else None)
            rows.append(line)
        merges = [[rlo, clo, rhi - rlo, chi - clo] for rlo, rhi, clo, chi in getattr(sheet, "merged_cells", [])]
        widths = {}
        if formatted:
            for c, info in getattr(sheet, "colinfo_map", {}).items():
                widths[c] = info.width / 256
        sheets.append(_sheet(sheet.name, rows, merges, sheet.nrows, sheet.ncols, widths))
    return sheets
