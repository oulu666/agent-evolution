"""Read-only SQLite tools and a deterministic fixture database."""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List

from .base import ToolError, ToolRegistry, require_str

MAX_ROWS = 100
BLOCKED = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|ATTACH|DETACH|"
    r"PRAGMA|VACUUM|REINDEX|TRIGGER)\b", re.IGNORECASE)


def create_fixture(path: str, force: bool = False) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if force and target.exists():
        target.unlink()
    connection = sqlite3.connect(str(target))
    try:
        cursor = connection.cursor()
        cursor.executescript(
            """
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY, name TEXT, department TEXT,
                salary REAL, age INTEGER
            );
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY, product TEXT, region TEXT,
                amount REAL, month TEXT
            );
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY, name TEXT, category TEXT,
                price REAL, stock INTEGER
            );
            """
        )
        for table, rows in _fixture_rows().items():
            cursor.execute("SELECT COUNT(*) FROM %s" % table)
            if cursor.fetchone()[0] == 0:
                placeholders = ",".join(["?"] * len(rows[0]))
                cursor.executemany(
                    "INSERT INTO %s VALUES (%s)" % (table, placeholders), rows)
        connection.commit()
    finally:
        connection.close()
    return target


def _fixture_rows() -> Dict[str, List[tuple]]:
    employees = [
        (1, "Alice", "Engineering", 120000.0, 34),
        (2, "Bob", "Sales", 82000.0, 29),
        (3, "Carol", "Engineering", 135000.0, 41),
        (4, "David", "HR", 68000.0, 37),
        (5, "Eve", "Sales", 91000.0, 31),
        (6, "Frank", "Finance", 105000.0, 45),
        (7, "Grace", "Engineering", 128000.0, 36),
        (8, "Heidi", "HR", 72000.0, 28),
        (9, "Ivan", "Sales", 88000.0, 33),
        (10, "Judy", "Finance", 99000.0, 39),
        (11, "Mallory", "Engineering", 142000.0, 44),
        (12, "Niaj", "Sales", 76000.0, 26),
    ]
    sales = [
        (1, "Widget", "North", 1200.5, "2026-01"),
        (2, "Gadget", "South", 800.0, "2026-01"),
        (3, "Widget", "East", 1500.75, "2026-02"),
        (4, "Doohickey", "West", 420.0, "2026-02"),
        (5, "Gadget", "North", 980.25, "2026-03"),
        (6, "Widget", "South", 1100.0, "2026-03"),
        (7, "Doohickey", "East", 640.5, "2026-04"),
        (8, "Gadget", "West", 720.0, "2026-04"),
        (9, "Widget", "North", 1300.0, "2026-05"),
        (10, "Doohickey", "South", 510.25, "2026-05"),
        (11, "Gadget", "East", 860.0, "2026-06"),
        (12, "Widget", "West", 1450.5, "2026-06"),
    ]
    products = [
        (1, "Widget", "Hardware", 19.99, 120),
        (2, "Gadget", "Hardware", 29.5, 80),
        (3, "Doohickey", "Hardware", 9.75, 200),
        (4, "Starter Kit", "Software", 49.0, 60),
        (5, "Pro Suite", "Software", 199.0, 25),
        (6, "Widget", "Hardware", 19.99, 140),
        (7, "Gadget", "Hardware", 29.5, 70),
        (8, "Data Pack", "Software", 79.0, 40),
        (9, "Cable", "Accessories", 4.5, 300),
        (10, "Adapter", "Accessories", 12.0, 150),
    ]
    return {"employees": employees, "sales": sales, "products": products}


def _quote_identifier(name: str) -> str:
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise ToolError("invalid SQL identifier")
    return '"%s"' % name


def _readonly_connection(path: str) -> sqlite3.Connection:
    target = Path(path).resolve().as_posix()
    connection = sqlite3.connect("file:%s?mode=ro" % target, uri=True)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only = ON")
    except sqlite3.Error:
        pass
    return connection


def _tables(path: str) -> List[str]:
    connection = _readonly_connection(path)
    try:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
        return [row[0] for row in rows]
    finally:
        connection.close()


def db_list_tables(path: str) -> List[str]:
    return _tables(path)


def db_schema(path: str, table: str) -> List[Dict[str, Any]]:
    if table not in _tables(path):
        raise ToolError("unknown table: %s" % table)
    connection = _readonly_connection(path)
    try:
        rows = connection.execute(
            "PRAGMA table_info(%s)" % _quote_identifier(table)).fetchall()
        return [{"name": row["name"], "type": row["type"],
                 "notnull": bool(row["notnull"]), "pk": bool(row["pk"])}
                for row in rows]
    finally:
        connection.close()


def db_query(path: str, sql: str) -> Dict[str, Any]:
    text = sql.strip()
    if not text:
        raise ToolError("sql must not be empty")
    if text.endswith(";"):
        text = text[:-1].strip()
    if ";" in text:
        raise ToolError("only one statement is allowed")
    first = text.split(None, 1)[0].upper()
    if first not in ("SELECT", "WITH"):
        raise ToolError("only SELECT or WITH queries are allowed")
    if BLOCKED.search(text):
        raise ToolError("query contains a forbidden keyword")
    connection = _readonly_connection(path)
    try:
        cursor = connection.execute(text)
        columns = [description[0] for description in cursor.description or []]
        rows = cursor.fetchmany(MAX_ROWS + 1)
        truncated = len(rows) > MAX_ROWS
        rows = rows[:MAX_ROWS]
        return {"columns": columns,
                "rows": [[row[column] for column in columns] for row in rows],
                "truncated": truncated}
    except sqlite3.Error as exc:
        raise ToolError("sqlite error: %s" % exc)
    finally:
        connection.close()


def build_db_registry(path: str) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        "db_list_tables",
        "List the table names in the read-only test database.",
        {"type": "object", "properties": {}, "additionalProperties": False},
        lambda args: db_list_tables(path),
    )
    registry.register(
        "db_schema",
        "Return the columns of one table in the read-only test database.",
        {"type": "object", "properties": {"table": {"type": "string"}},
         "required": ["table"], "additionalProperties": False},
        lambda args: db_schema(path, require_str(args, "table")),
    )
    registry.register(
        "db_query",
        "Run one read-only SELECT or WITH query and return columns and up to 100 rows.",
        {"type": "object", "properties": {"sql": {"type": "string"}},
         "required": ["sql"], "additionalProperties": False},
        lambda args: db_query(path, require_str(args, "sql", max_length=2048)),
    )
    return registry
