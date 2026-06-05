import re
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd


OUTPUT_COLUMNS = [
    "report_date",
    "theme_name",
    "stock_name",
    "change_rate",
    "trading_value",
    "pdf_file_name",
    "raw_line",
]


DATE_PATTERNS = [
    re.compile(r"(20\d{2})[-._/](\d{1,2})[-._/](\d{1,2})"),
    re.compile(r"(20\d{2})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일"),
]
STOCK_ITEM_PATTERN = re.compile(
    r"●?\s*(?P<stock_name>[^()/,]+?)\s*"
    r"\((?P<change_rate>[+-]?\d+(?:\.\d+)?)\s*%\)\s*"
    r"\((?P<trading_value>[\d,]+(?:\.\d+)?)\)"
)
THEME_MARKERS = ("테마", "Theme", "THEME")
HEADER_WORDS = ("종목", "등락률", "거래대금", "전일대비")


def find_pdf_files(pdf_dir: str | Path, limit: int | None = None) -> list[Path]:
    path = Path(pdf_dir)
    if not path.exists():
        return []

    pdf_files = sorted(path.glob("*.pdf"))
    if limit is not None:
        return pdf_files[:limit]
    return pdf_files


def extract_pdf_text(pdf_path: str | Path) -> str:
    try:
        from pypdf import PdfReader
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "pypdf is required to extract PDF text. Install requirements.txt first."
        ) from exc

    reader = PdfReader(str(pdf_path))
    page_texts = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(page_texts)


def parse_signal_evening_pdf(pdf_path: str | Path) -> pd.DataFrame:
    path = Path(pdf_path)
    text = extract_pdf_text(path)
    return parse_signal_evening_text(text, path.name)


def parse_signal_evening_text(text: str, pdf_file_name: str) -> pd.DataFrame:
    report_date = _extract_report_date(pdf_file_name, text)
    current_theme = "미분류"
    rows: list[dict[str, Any]] = []

    for line in _iter_logical_lines(text):
        theme_name = _extract_theme_name(line)
        if theme_name is not None:
            current_theme = theme_name
            continue

        items = _parse_item_line(line, current_theme)
        if items is None:
            continue

        for item in items:
            rows.append(
                {
                    "report_date": report_date,
                    "theme_name": item["theme_name"],
                    "stock_name": item["stock_name"],
                    "change_rate": item["change_rate"],
                    "trading_value": item["trading_value"],
                    "pdf_file_name": pdf_file_name,
                    "raw_line": line,
                }
            )

    return pd.DataFrame(rows, columns=OUTPUT_COLUMNS)


def parse_signal_evening_pdfs(
    pdf_dir: str | Path = "data/pdfs",
    limit: int | None = None,
) -> pd.DataFrame:
    frames = [
        parse_signal_evening_pdf(pdf_path)
        for pdf_path in find_pdf_files(pdf_dir, limit=limit)
    ]
    frames = [frame for frame in frames if not frame.empty]

    if not frames:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)
    return pd.concat(frames, ignore_index=True)


def _extract_report_date(pdf_file_name: str, text: str) -> date | None:
    source = f"{pdf_file_name}\n{text[:2000]}"
    for pattern in DATE_PATTERNS:
        match = pattern.search(source)
        if match:
            year, month, day = (int(value) for value in match.groups())
            return date(year, month, day)
    return None


def _normalize_line(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _iter_logical_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw_line in text.splitlines():
        line = _normalize_line(raw_line)
        if not line:
            continue

        wrapped_item_pattern = r"^\(([+-]?\d+(?:\.\d+)?\s*%|[\d,]+(?:\.\d+)?)\)"
        if lines and re.match(wrapped_item_pattern, line):
            lines[-1] = f"{lines[-1]} {line}"
            continue

        lines.append(line)

    return lines


def _extract_theme_name(line: str) -> str | None:
    if any(word in line for word in HEADER_WORDS):
        return None

    bracket_match = re.match(r"^<\s*(.+?)\s*>$", line)
    if bracket_match:
        return bracket_match.group(1).strip()

    if not any(marker in line for marker in THEME_MARKERS):
        return None

    cleaned = re.sub(r"^[\-\*\d.\s]+", "", line)
    cleaned = re.sub(r"^(테마명|테마)\s*[:：-]?\s*", "", cleaned)
    cleaned = re.sub(r"\s*(테마)$", "", cleaned)
    return cleaned.strip() or None


def _parse_item_line(line: str, current_theme: str) -> list[dict[str, Any]] | None:
    items: list[dict[str, Any]] = []
    for match in STOCK_ITEM_PATTERN.finditer(line):
        stock_name = _clean_stock_name(match.group("stock_name"))
        if not stock_name:
            continue

        items.append(
            {
                "theme_name": current_theme,
                "stock_name": stock_name,
                "change_rate": Decimal(match.group("change_rate")),
                "trading_value": Decimal(
                    match.group("trading_value").replace(",", "")
                ),
            }
        )

    if items:
        return items

    return None


def _clean_stock_name(value: str) -> str | None:
    cleaned = re.sub(r"^[●\-\*\d.)\s]+", "", value).strip(" |/\t")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned or None
