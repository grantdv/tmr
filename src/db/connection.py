import os
from contextlib import contextmanager
from typing import Iterator

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

load_dotenv()


def get_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is not configured. Copy .env.example to .env and set DATABASE_URL."
        )
    return database_url


def get_engine() -> Engine:
    return create_engine(get_database_url(), pool_pre_ping=True)


@contextmanager
def get_db_connection() -> Iterator[Connection]:
    engine = get_engine()
    connection = engine.connect()
    try:
        yield connection
    finally:
        connection.close()
        engine.dispose()


def check_db_connection() -> bool:
    with get_db_connection() as connection:
        connection.execute(text("SELECT 1"))
    return True
