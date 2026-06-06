from database.db import get_connection


THEME_ALIAS_SEED = [
    ("삼성 / 반디플", "반도체"),
    ("삼성 # 반디플", "반도체"),
    ("반 / 디플", "반도체"),
    ("반도체", "반도체"),
    ("전력 / 에너지", "전력"),
    ("전선", "전력"),
    ("BIO / 의료AI", "바이오"),
    ("BIO", "바이오"),
    ("의료AI", "바이오"),
    ("로봇 / AI", "AI/로봇"),
    ("로봇", "AI/로봇"),
    ("AI", "AI/로봇"),
    ("코인 / 가상 자산", "코인/가상자산"),
    ("코인 / 가상자산", "코인/가상자산"),
    ("정부 정책", "정부정책"),
    ("정부정책", "정부정책"),
]


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


def seed_theme_aliases() -> dict[str, int]:
    upsert_alias_sql = """
        INSERT INTO theme_alias (
            alias_name,
            theme_id,
            canonical_name
        )
        SELECT
            %(alias_name)s,
            (
                SELECT id
                FROM theme_master
                WHERE theme_name = %(alias_name)s
            ),
            %(canonical_name)s
        ON CONFLICT (alias_name)
        DO UPDATE SET
            theme_id = EXCLUDED.theme_id,
            canonical_name = EXCLUDED.canonical_name
        RETURNING id
    """

    canonical_names = sorted({canonical for _, canonical in THEME_ALIAS_SEED})

    with get_connection() as connection:
        with connection.cursor() as cursor:
            alias_count = 0
            for alias_name, canonical_name in THEME_ALIAS_SEED:
                cursor.execute(
                    upsert_alias_sql,
                    {
                        "alias_name": alias_name,
                        "canonical_name": canonical_name,
                    },
                )
                if cursor.fetchone() is not None:
                    alias_count += 1

        connection.commit()

    return {
        "canonical_theme_count": len(canonical_names),
        "alias_count": alias_count,
    }


def build_stock_canonical_theme_map() -> dict[str, int]:
    upsert_sql = """
        WITH mapped AS (
            SELECT
                s.stock_name,
                COALESCE(a.canonical_name, t.theme_name) AS canonical_theme,
                s.first_seen_date,
                s.last_seen_date,
                s.hit_count,
                s.avg_change_rate,
                s.max_change_rate,
                s.total_trading_value
            FROM stock_theme_map s
            JOIN theme_master t
                ON t.id = s.theme_id
            LEFT JOIN theme_alias a
                ON a.alias_name = t.theme_name
        ),
        aggregated AS (
            SELECT
                stock_name,
                canonical_theme,
                MIN(first_seen_date) AS first_seen_date,
                MAX(last_seen_date) AS last_seen_date,
                SUM(hit_count)::integer AS hit_count,
                ROUND(
                    SUM(avg_change_rate * hit_count)
                    / NULLIF(
                        SUM(
                            CASE
                                WHEN avg_change_rate IS NOT NULL THEN hit_count
                                ELSE 0
                            END
                        ),
                        0
                    ),
                    2
                ) AS avg_change_rate,
                MAX(max_change_rate) AS max_change_rate,
                SUM(COALESCE(total_trading_value, 0)) AS total_trading_value
            FROM mapped
            WHERE TRIM(stock_name) <> ''
                AND TRIM(canonical_theme) <> ''
            GROUP BY
                stock_name,
                canonical_theme
        )
        INSERT INTO stock_canonical_theme_map (
            stock_name,
            canonical_theme,
            first_seen_date,
            last_seen_date,
            hit_count,
            avg_change_rate,
            max_change_rate,
            total_trading_value
        )
        SELECT
            stock_name,
            canonical_theme,
            first_seen_date,
            last_seen_date,
            hit_count,
            avg_change_rate,
            max_change_rate,
            total_trading_value
        FROM aggregated
        ON CONFLICT (stock_name, canonical_theme)
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
            cursor.execute(upsert_sql)
            stock_canonical_theme_map_count = len(cursor.fetchall())
        connection.commit()

    return {
        "stock_canonical_theme_map_count": stock_canonical_theme_map_count,
    }
