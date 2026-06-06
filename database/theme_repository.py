from database.db import get_connection


CANONICAL_THEME_SEED = [
    ("반도체", "IT/제조", "반도체, 디스플레이, HBM, AI 반도체 관련 테마", 10),
    ("바이오", "헬스케어", "제약, 바이오, 의료AI, 의료기기 관련 테마", 20),
    ("AI/로봇", "IT/자동화", "AI, 로봇, 휴머노이드, 자동화 관련 테마", 30),
    ("전력", "인프라", "전력망, 전선, 변압기, 전력기기 관련 테마", 40),
    ("에너지", "에너지", "태양광, 풍력, 수소, 탄소, 에너지 가격 관련 테마", 50),
    ("원전", "에너지", "원전, 원자력, SMR 관련 테마", 60),
    ("이차전지", "미래차/배터리", "배터리, ESS, 소재, 장비 관련 테마", 70),
    ("미래차", "미래차/배터리", "자동차, 전기차, 자율주행, 현대차 관련 테마", 80),
    ("조선", "산업재", "조선, 선박, LNG선 관련 테마", 90),
    ("방산", "산업재", "방산, 우주항공, 드론 관련 테마", 100),
    ("COVID19", "헬스케어", "코로나19, 감염병, 진단키트 관련 테마", 105),
    ("우주항공", "산업재", "우주, 항공, 위성, UAM 관련 테마", 106),
    ("중동전쟁", "매크로/지정학", "중동전쟁, 지정학 리스크 관련 테마", 107),
    ("코인/가상자산", "금융/디지털자산", "코인, 가상자산, STO 관련 테마", 110),
    ("정부정책", "정책", "정부 정책, 선거, 정책 수혜 관련 테마", 120),
    ("엔터/IP", "콘텐츠", "엔터, IP, 콘텐츠, 게임, 웹툰 관련 테마", 130),
    ("통신/보안", "IT/인프라", "통신, 보안, 데이터센터 관련 테마", 140),
    ("원자재", "소재", "원자재, 금속, 곡물 등 상품 가격 관련 테마", 150),
    ("실적/공시", "이벤트", "실적, 공시, 수주 등 개별 이벤트 테마", 160),
    ("M&A", "이벤트", "인수합병, 지분, 경영권 관련 테마", 170),
    ("개별주", "기타", "별도 표준 테마로 묶기 어려운 개별 종목 이슈", 999),
]


THEME_ALIAS_SEED = [
    ("삼성", "반도체"),
    ("삼성 / 반디플", "반도체"),
    ("삼성 # 반디플", "반도체"),
    ("반 / 디플", "반도체"),
    ("반도체", "반도체"),
    ("삼성 / 반도체", "반도체"),
    ("AI반도체", "반도체"),
    ("AI 반도체", "반도체"),
    ("HBM", "반도체"),
    ("온디바이스AI", "반도체"),
    ("온디바이스 AI", "반도체"),
    ("유리기판", "반도체"),
    ("디스플레이", "반도체"),
    ("반디플", "반도체"),
    ("칩렛", "반도체"),
    ("CXL", "반도체"),
    ("소부장", "반도체"),
    ("BIO / 미용", "바이오"),
    ("BIO / 의료", "바이오"),
    ("전력 / 에너지", "전력"),
    ("전선", "전력"),
    ("BIO / 의료AI", "바이오"),
    ("BIO", "바이오"),
    ("의료AI", "바이오"),
    ("제약", "바이오"),
    ("비만치료제", "바이오"),
    ("의료기기", "바이오"),
    ("미용", "바이오"),
    ("화장품", "바이오"),
    ("헬스케어", "바이오"),
    ("치매", "바이오"),
    ("암", "바이오"),
    ("AI / 로봇", "AI/로봇"),
    ("AI/로봇", "AI/로봇"),
    ("로봇 / AI", "AI/로봇"),
    ("로봇", "AI/로봇"),
    ("AI", "AI/로봇"),
    ("로봇 / 자동차", "AI/로봇"),
    ("로봇 / IT", "AI/로봇"),
    ("로봇 / 이차전지", "AI/로봇"),
    ("현대차 / 로봇", "AI/로봇"),
    ("휴머노이드", "AI/로봇"),
    ("자동화", "AI/로봇"),
    ("챗GPT", "AI/로봇"),
    ("AI / 소프트웨어", "AI/로봇"),
    ("전력", "전력"),
    ("변압기", "전력"),
    ("전력설비", "전력"),
    ("전력기기", "전력"),
    ("전력망", "전력"),
    ("초전도체", "전력"),
    ("에너지", "에너지"),
    ("중동전쟁 / 에너지", "에너지"),
    ("CO2 # 에너지", "에너지"),
    ("태양광", "에너지"),
    ("풍력", "에너지"),
    ("수소", "에너지"),
    ("탄소", "에너지"),
    ("유가", "에너지"),
    ("원전", "원전"),
    ("원전 / 에너지", "원전"),
    ("원자력", "원전"),
    ("SMR", "원전"),
    ("이차전지", "이차전지"),
    ("미래차 # 이차전지", "이차전지"),
    ("이차전지 / ESS", "이차전지"),
    ("이차전지 / 자동차", "이차전지"),
    ("자동차 / 이차전지", "이차전지"),
    ("배터리", "이차전지"),
    ("ESS", "이차전지"),
    ("리튬", "이차전지"),
    ("양극재", "이차전지"),
    ("음극재", "이차전지"),
    ("전고체", "이차전지"),
    ("미래차", "미래차"),
    ("미래차 # 이차전지 #UAM", "미래차"),
    ("자동차", "미래차"),
    ("자율주행", "미래차"),
    ("전기차", "미래차"),
    ("현대차", "미래차"),
    ("테슬라", "미래차"),
    ("차량용반도체", "미래차"),
    ("방산", "방산"),
    ("중동전쟁 / 방산", "방산"),
    ("조선 / 방산", "방산"),
    ("우주 / 방산", "방산"),
    ("방산 / 중동", "방산"),
    ("드론", "방산"),
    ("우주", "우주항공"),
    ("우주 / 항공", "우주항공"),
    ("우주항공", "우주항공"),
    ("항공우주", "우주항공"),
    ("UAM", "우주항공"),
    ("조선", "조선"),
    ("선박", "조선"),
    ("LNG선", "조선"),
    ("해운", "조선"),
    ("코인 / 가상 자산", "코인/가상자산"),
    ("코인 / 가상자산", "코인/가상자산"),
    ("코인/가상자산", "코인/가상자산"),
    ("가상자산", "코인/가상자산"),
    ("가상 자산 # 가상 현실", "코인/가상자산"),
    ("STO", "코인/가상자산"),
    ("비트코인", "코인/가상자산"),
    ("두나무", "코인/가상자산"),
    ("정부 정책", "정부정책"),
    ("정부정책", "정부정책"),
    ("제21대 대선", "정부정책"),
    ("정책", "정부정책"),
    ("상법 개정", "정부정책"),
    ("대선", "정부정책"),
    ("저출산", "정부정책"),
    ("IP # 엔터", "엔터/IP"),
    ("IP / 엔터", "엔터/IP"),
    ("엔터", "엔터/IP"),
    ("콘텐츠", "엔터/IP"),
    ("게임", "엔터/IP"),
    ("웹툰", "엔터/IP"),
    ("음원", "엔터/IP"),
    ("영화", "엔터/IP"),
    ("IT / 통신", "통신/보안"),
    ("통신 / 보안", "통신/보안"),
    ("보안", "통신/보안"),
    ("통신", "통신/보안"),
    ("데이터센터", "통신/보안"),
    ("클라우드", "통신/보안"),
    ("5G", "통신/보안"),
    ("원자재", "원자재"),
    ("중동전쟁 / 원자재", "원자재"),
    ("구리", "원자재"),
    ("철강", "원자재"),
    ("알루미늄", "원자재"),
    ("금", "원자재"),
    ("곡물", "원자재"),
    ("실적 / 공시", "실적/공시"),
    ("공시", "실적/공시"),
    ("실적", "실적/공시"),
    ("수주", "실적/공시"),
    ("M ＆ A 공시", "M&A"),
    ("M&A", "M&A"),
    ("인수합병", "M&A"),
    ("지분", "M&A"),
    ("개별주", "개별주"),
    ("COVID19", "COVID19"),
    ("코로나 19", "COVID19"),
    ("COVID-19", "COVID19"),
    ("BIO #COVID19", "COVID19"),
    ("COVID19 # 코로나 회전문", "COVID19"),
    ("중동전쟁", "중동전쟁"),
    ("미중패권분쟁", "중동전쟁"),
]


STOCK_KEYWORD_SEED = {
    "한미반도체": [
        "HBM",
        "AI반도체",
        "SK하이닉스",
        "엔비디아",
        "반도체 장비",
    ],
    "SK하이닉스": [
        "HBM",
        "AI반도체",
        "엔비디아",
        "메모리반도체",
        "D램",
    ],
    "삼성전자": [
        "HBM",
        "AI반도체",
        "엔비디아",
        "반도체",
        "메모리반도체",
    ],
    "LS ELECTRIC": [
        "전력설비",
        "전력기기",
        "변압기",
        "데이터센터",
        "AI전력",
    ],
    "두산에너빌리티": [
        "원전",
        "SMR",
        "전력",
        "가스터빈",
        "에너지",
    ],
    "로보티즈": [
        "로봇",
        "휴머노이드",
        "자율주행로봇",
        "AI로봇",
    ],
    "현대차": [
        "로봇",
        "전기차",
        "자율주행",
        "수소차",
        "미래차",
    ],
    "알테오젠": [
        "바이오",
        "ADC",
        "항체의약품",
        "기술수출",
        "제약바이오",
    ],
}


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


def seed_canonical_themes() -> dict[str, int]:
    upsert_sql = """
        INSERT INTO canonical_theme_master (
            canonical_name,
            category_name,
            description,
            priority,
            is_active
        )
        VALUES (
            %(canonical_name)s,
            %(category_name)s,
            %(description)s,
            %(priority)s,
            TRUE
        )
        ON CONFLICT (canonical_name)
        DO UPDATE SET
            category_name = EXCLUDED.category_name,
            description = EXCLUDED.description,
            priority = EXCLUDED.priority,
            is_active = EXCLUDED.is_active,
            updated_at = NOW()
        RETURNING id
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            seed_count = 0
            for canonical_name, category_name, description, priority in CANONICAL_THEME_SEED:
                cursor.execute(
                    upsert_sql,
                    {
                        "canonical_name": canonical_name,
                        "category_name": category_name,
                        "description": description,
                        "priority": priority,
                    },
                )
                if cursor.fetchone() is not None:
                    seed_count += 1
        connection.commit()

    return {"canonical_theme_count": seed_count}


def seed_theme_aliases() -> dict[str, int]:
    upsert_alias_sql = """
        INSERT INTO theme_alias (
            alias_name,
            theme_id,
            canonical_name,
            canonical_theme_id,
            match_type,
            memo,
            is_active
        )
        SELECT
            %(alias_name)s,
            (
                SELECT id
                FROM theme_master
                WHERE theme_name = %(alias_name)s
            ),
            %(canonical_name)s,
            c.id,
            'seed',
            'initial canonical theme seed',
            TRUE
        FROM canonical_theme_master c
        WHERE c.canonical_name = %(canonical_name)s
        ON CONFLICT (alias_name)
        DO UPDATE SET
            theme_id = EXCLUDED.theme_id,
            canonical_name = EXCLUDED.canonical_name,
            canonical_theme_id = EXCLUDED.canonical_theme_id,
            match_type = EXCLUDED.match_type,
            memo = EXCLUDED.memo,
            is_active = EXCLUDED.is_active
        RETURNING id
    """

    canonical_names = sorted({canonical for _, canonical in THEME_ALIAS_SEED})

    with get_connection() as connection:
        with connection.cursor() as cursor:
            missing_canonical_names: set[str] = set()
            alias_count = 0
            for alias_name, canonical_name in THEME_ALIAS_SEED:
                cursor.execute(
                    upsert_alias_sql,
                    {
                        "alias_name": alias_name,
                        "canonical_name": canonical_name,
                    },
                )
                row = cursor.fetchone()
                if row is not None:
                    alias_count += 1
                else:
                    missing_canonical_names.add(canonical_name)

        connection.commit()

    return {
        "canonical_theme_count": len(canonical_names),
        "alias_count": alias_count,
        "missing_canonical_theme_count": len(missing_canonical_names),
    }


def seed_stock_keywords() -> dict[str, int | list[str]]:
    upsert_sql = """
        INSERT INTO stock_keyword_map (
            stock_code,
            stock_name,
            keyword,
            keyword_type,
            weight,
            is_active
        )
        SELECT
            stock_code,
            stock_name,
            %(keyword)s,
            'seed',
            1.0,
            TRUE
        FROM stock_master
        WHERE stock_name = %(stock_name)s
        ON CONFLICT (stock_code, keyword)
        DO UPDATE SET
            stock_name = EXCLUDED.stock_name,
            keyword_type = EXCLUDED.keyword_type,
            weight = EXCLUDED.weight,
            is_active = TRUE
        RETURNING id
    """

    seeded_count = 0
    missing_stocks: list[str] = []

    with get_connection() as connection:
        with connection.cursor() as cursor:
            for stock_name, keywords in STOCK_KEYWORD_SEED.items():
                stock_seeded_count = 0
                for keyword in keywords:
                    cursor.execute(
                        upsert_sql,
                        {
                            "stock_name": stock_name,
                            "keyword": keyword,
                        },
                    )
                    if cursor.fetchone() is not None:
                        seeded_count += 1
                        stock_seeded_count += 1

                if stock_seeded_count == 0:
                    missing_stocks.append(stock_name)

        connection.commit()

    return {
        "seeded_count": seeded_count,
        "stock_count": len(STOCK_KEYWORD_SEED),
        "missing_stocks": missing_stocks,
    }


def build_stock_canonical_theme_map() -> dict[str, int]:
    upsert_sql = """
        WITH mapped AS (
            SELECT
                s.stock_name,
                COALESCE(c.canonical_name, a.canonical_name, t.theme_name)
                    AS canonical_theme,
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
                AND a.is_active = TRUE
            LEFT JOIN canonical_theme_master c
                ON c.id = a.canonical_theme_id
                AND c.is_active = TRUE
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


def build_stock_profiles() -> dict[str, int]:
    upsert_sql = """
        WITH ranked AS (
            SELECT
                stock_name,
                canonical_theme,
                first_seen_date,
                last_seen_date,
                hit_count,
                ROW_NUMBER() OVER (
                    PARTITION BY stock_name
                    ORDER BY hit_count DESC, canonical_theme
                ) AS theme_rank
            FROM stock_canonical_theme_map
            WHERE TRIM(stock_name) <> ''
                AND TRIM(canonical_theme) <> ''
        ),
        aggregated AS (
            SELECT
                stock_name,
                MAX(canonical_theme) FILTER (WHERE theme_rank = 1)
                    AS primary_theme,
                MAX(canonical_theme) FILTER (WHERE theme_rank = 2)
                    AS secondary_theme,
                STRING_AGG(
                    canonical_theme,
                    ', '
                    ORDER BY hit_count DESC, canonical_theme
                ) AS related_themes,
                COUNT(*)::integer AS theme_count,
                SUM(hit_count)::integer AS total_hit_count,
                MIN(first_seen_date) AS first_seen_date,
                MAX(last_seen_date) AS last_seen_date,
                SUM(hit_count)::numeric(20, 2) AS profile_score
            FROM ranked
            GROUP BY stock_name
        )
        INSERT INTO stock_profile (
            stock_name,
            primary_theme,
            secondary_theme,
            related_themes,
            theme_count,
            total_hit_count,
            first_seen_date,
            last_seen_date,
            profile_score
        )
        SELECT
            stock_name,
            primary_theme,
            secondary_theme,
            related_themes,
            theme_count,
            total_hit_count,
            first_seen_date,
            last_seen_date,
            profile_score
        FROM aggregated
        ON CONFLICT (stock_name)
        DO UPDATE SET
            primary_theme = EXCLUDED.primary_theme,
            secondary_theme = EXCLUDED.secondary_theme,
            related_themes = EXCLUDED.related_themes,
            theme_count = EXCLUDED.theme_count,
            total_hit_count = EXCLUDED.total_hit_count,
            first_seen_date = EXCLUDED.first_seen_date,
            last_seen_date = EXCLUDED.last_seen_date,
            profile_score = EXCLUDED.profile_score,
            updated_at = NOW()
        RETURNING id
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(upsert_sql)
            stock_profile_count = len(cursor.fetchall())
        connection.commit()

    return {"stock_profile_count": stock_profile_count}


def build_stock_knowledge_graph() -> dict[str, int]:
    upsert_theme_sql = """
        WITH raw_nodes AS (
            SELECT
                TRIM(stock_name) AS stock_name,
                'THEME' AS node_type,
                TRIM(primary_theme) AS node_value,
                'PRIMARY_THEME' AS relation_type,
                'stock_profile' AS source,
                100::numeric(10, 2) AS score
            FROM stock_profile
            WHERE primary_theme IS NOT NULL
                AND TRIM(primary_theme) <> ''

            UNION ALL

            SELECT
                TRIM(stock_name) AS stock_name,
                'THEME' AS node_type,
                TRIM(secondary_theme) AS node_value,
                'SECONDARY_THEME' AS relation_type,
                'stock_profile' AS source,
                70::numeric(10, 2) AS score
            FROM stock_profile
            WHERE secondary_theme IS NOT NULL
                AND TRIM(secondary_theme) <> ''

            UNION ALL

            SELECT
                TRIM(p.stock_name) AS stock_name,
                'THEME' AS node_type,
                TRIM(theme_value) AS node_value,
                'RELATED_THEME' AS relation_type,
                'stock_profile' AS source,
                50::numeric(10, 2) AS score
            FROM stock_profile p
            CROSS JOIN LATERAL regexp_split_to_table(
                COALESCE(p.related_themes, ''),
                '\\s*,\\s*'
            ) AS theme_value
            WHERE TRIM(theme_value) <> ''
                AND TRIM(theme_value) <> COALESCE(TRIM(p.primary_theme), '')
                AND TRIM(theme_value) <> COALESCE(TRIM(p.secondary_theme), '')
        ),
        dedup_nodes AS (
            SELECT
                stock_name,
                node_type,
                node_value,
                relation_type,
                MIN(source) AS source,
                MAX(score) AS score
            FROM raw_nodes
            WHERE stock_name <> ''
                AND node_value <> ''
            GROUP BY
                stock_name,
                node_type,
                node_value,
                relation_type
        )
        INSERT INTO stock_knowledge_graph (
            stock_name,
            node_type,
            node_value,
            relation_type,
            source,
            score
        )
        SELECT
            stock_name,
            node_type,
            node_value,
            relation_type,
            source,
            score
        FROM dedup_nodes
        ON CONFLICT (stock_name, node_type, node_value, relation_type)
        DO UPDATE SET
            source = EXCLUDED.source,
            score = EXCLUDED.score,
            updated_at = NOW()
        RETURNING id
    """

    upsert_keyword_sql = """
        WITH raw_nodes AS (
            SELECT
                TRIM(m.stock_name) AS stock_name,
                'KEYWORD' AS node_type,
                TRIM(k.keyword) AS node_value,
                'STOCK_KEYWORD' AS relation_type,
                'stock_keyword_map' AS source,
                80::numeric(10, 2) AS score
            FROM stock_keyword_map k
            JOIN stock_master m
                ON m.stock_code = k.stock_code
            WHERE k.is_active = TRUE
                AND TRIM(k.keyword) <> ''
                AND TRIM(m.stock_name) <> ''
        ),
        dedup_nodes AS (
            SELECT
                stock_name,
                node_type,
                node_value,
                relation_type,
                MIN(source) AS source,
                MAX(score) AS score
            FROM raw_nodes
            GROUP BY
                stock_name,
                node_type,
                node_value,
                relation_type
        )
        INSERT INTO stock_knowledge_graph (
            stock_name,
            node_type,
            node_value,
            relation_type,
            source,
            score
        )
        SELECT
            stock_name,
            node_type,
            node_value,
            relation_type,
            source,
            score
        FROM dedup_nodes
        ON CONFLICT (stock_name, node_type, node_value, relation_type)
        DO UPDATE SET
            source = EXCLUDED.source,
            score = EXCLUDED.score,
            updated_at = NOW()
        RETURNING id
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(upsert_theme_sql)
            theme_node_count = len(cursor.fetchall())

            cursor.execute(upsert_keyword_sql)
            keyword_node_count = len(cursor.fetchall())

        connection.commit()

    return {
        "theme_node_count": theme_node_count,
        "keyword_node_count": keyword_node_count,
        "stock_knowledge_graph_count": theme_node_count + keyword_node_count,
    }


def get_expanded_search_terms(stock_name: str, limit: int = 20) -> list[str]:
    query = """
        SELECT node_value
        FROM stock_knowledge_graph
        WHERE stock_name = %(stock_name)s
        ORDER BY score DESC, node_type, node_value
        LIMIT %(limit)s
    """

    terms = [stock_name]
    seen = {stock_name}

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, {"stock_name": stock_name, "limit": limit})
            for row in cursor.fetchall():
                term = row[0]
                if not term or term in seen:
                    continue
                seen.add(term)
                terms.append(term)

    return terms
