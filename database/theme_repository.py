from database.db import get_connection


def build_stock_theme_map() -> dict[str, int]:
    insert_themes_sql = """
        INSERT INTO theme_master (theme_name)
        SELECT DISTINCT TRIM(theme_name) AS theme_name
        FROM pdf_signal_item
        WHERE TRIM(theme_name) <> ''
        ON CONFLICT (theme_name) DO NOTHING
    """

    theme_count_sql = """
        SELECT COUNT(*)
        FROM theme_master
    """

    upsert_map_sql = """
        WITH aggregated AS (
            SELECT
                TRIM(p.stock_name) AS stock_name,
                t.id AS theme_id,
                MIN(p.report_date) AS first_seen_date,
                MAX(p.report_date) AS last_seen_date,
                COUNT(*)::integer AS hit_count,
                ROUND(AVG(p.change_rate), 2) AS avg_change_rate,
                MAX(p.change_rate) AS max_change_rate,
                SUM(COALESCE(p.trading_value, 0)) AS total_trading_value
            FROM pdf_signal_item p
            JOIN theme_master t
                ON t.theme_name = TRIM(p.theme_name)
            WHERE TRIM(p.stock_name) <> ''
                AND TRIM(p.theme_name) <> ''
            GROUP BY
                TRIM(p.stock_name),
                t.id
        )
        INSERT INTO stock_theme_map (
            stock_name,
            theme_id,
            first_seen_date,
            last_seen_date,
            hit_count,
            avg_change_rate,
            max_change_rate,
            total_trading_value
        )
        SELECT
            stock_name,
            theme_id,
            first_seen_date,
            last_seen_date,
            hit_count,
            avg_change_rate,
            max_change_rate,
            total_trading_value
        FROM aggregated
        ON CONFLICT (stock_name, theme_id)
        DO UPDATE SET
            first_seen_date = EXCLUDED.first_seen_date,
            last_seen_date = EXCLUDED.last_seen_date,
            hit_count = EXCLUDED.hit_count,
            avg_change_rate = EXCLUDED.avg_change_rate,
            max_change_rate = EXCLUDED.max_change_rate,
            total_trading_value = EXCLUDED.total_trading_value,
            updated_at = NOW()
        RETURNING id
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(insert_themes_sql)

            cursor.execute(theme_count_sql)
            theme_count = cursor.fetchone()[0]

            cursor.execute(upsert_map_sql)
            stock_theme_map_count = len(cursor.fetchall())

        connection.commit()

    return {
        "theme_count": theme_count,
        "stock_theme_map_count": stock_theme_map_count,
    }
