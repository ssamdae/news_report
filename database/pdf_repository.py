from typing import Any

import pandas as pd

from database.db import get_connection


PDF_SIGNAL_COLUMNS = [
    "report_date",
    "theme_name",
    "stock_name",
    "change_rate",
    "trading_value",
    "pdf_file_name",
    "raw_line",
]


def _clean_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def _records_from_dataframe(df: pd.DataFrame) -> list[dict[str, Any]]:
    missing_columns = set(PDF_SIGNAL_COLUMNS) - set(df.columns)
    if missing_columns:
        raise ValueError(
            "Missing required PDF signal columns: "
            + ", ".join(sorted(missing_columns))
        )

    records = df[PDF_SIGNAL_COLUMNS].to_dict("records")
    return [
        {key: _clean_value(value) for key, value in record.items()}
        for record in records
    ]


def save_pdf_signal_items(df: pd.DataFrame) -> int:
    if df.empty:
        return 0

    rows = _records_from_dataframe(df)
    if not rows:
        return 0

    sql = """
        INSERT INTO pdf_signal_item (
            report_date,
            theme_name,
            stock_name,
            change_rate,
            trading_value,
            pdf_file_name,
            raw_line
        )
        VALUES (
            %(report_date)s,
            %(theme_name)s,
            %(stock_name)s,
            %(change_rate)s,
            %(trading_value)s,
            %(pdf_file_name)s,
            %(raw_line)s
        )
        ON CONFLICT (
            pdf_file_name,
            theme_name,
            stock_name,
            change_rate,
            trading_value
        ) DO NOTHING
        RETURNING id
    """

    inserted_count = 0
    with get_connection() as connection:
        with connection.cursor() as cursor:
            for row in rows:
                cursor.execute(sql, row)
                if cursor.fetchone() is not None:
                    inserted_count += 1
        connection.commit()

    return inserted_count
