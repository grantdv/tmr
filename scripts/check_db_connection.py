#!/usr/bin/env python3
"""Check PostgreSQL connectivity using DATABASE_URL from .env."""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from db.connection import check_db_connection, get_database_url  # noqa: E402


def mask_database_url(url: str) -> str:
    if "://" not in url or "@" not in url:
        return url
    scheme, rest = url.split("://", 1)
    credentials, host_part = rest.split("@", 1)
    if ":" in credentials:
        user, _password = credentials.split(":", 1)
        return f"{scheme}://{user}:***@{host_part}"
    return f"{scheme}://***@{host_part}"


def main() -> int:
    try:
        database_url = get_database_url()
        print(f"DATABASE_URL: {mask_database_url(database_url)}")
        check_db_connection()
        print("Database connection: OK")
        return 0
    except Exception as exc:
        print(f"Database connection: FAILED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
