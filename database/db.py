import os
from collections.abc import Iterator
from contextlib import contextmanager


def load_environment() -> None:
    try:
        from dotenv import load_dotenv
    except ModuleNotFoundError:
        return

    load_dotenv()


def get_database_url() -> str:
    load_environment()

    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "stock_research")
    user = os.getenv("DB_USER", "stock_user")
    password = os.getenv("DB_PASSWORD", "")

    return (
        f"host={host} "
        f"port={port} "
        f"dbname={db_name} "
        f"user={user} "
        f"password={password}"
    )


@contextmanager
def get_connection() -> Iterator:
    import psycopg

    with psycopg.connect(get_database_url()) as connection:
        yield connection


def test_connection() -> bool:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
    return result == (1,)
