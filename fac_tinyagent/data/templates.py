"""Task templates for the three deterministic tool families.

Every template belongs to exactly one split.  Entities are generated from a
split-specific seed, so a test task is never a surface rewrite of a train task.
"""
from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from typing import Any, Dict, List

from ..tools.calendar_tools import EVENTS

FILE_WORDS = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot",
              "golf", "hotel", "india", "juliet", "kilo", "lima"]


@dataclass
class Template:
    template_id: str
    family: str
    split: str
    skills: List[str]
    build: Any


def stable_rng(seed: int, family: str, template_id: str, split: str,
               index: int) -> random.Random:
    key = "%s|%s|%s|%s|%d" % (seed, family, template_id, split, index)
    value = int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:16], 16)
    return random.Random(value)


def as_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


# ---------------------------------------------------------------------------
# File family
# ---------------------------------------------------------------------------

def _file_case(rng: random.Random, split: str, index: int, kind: str) -> Dict[str, Any]:
    path = "%s/%s_%02d.txt" % (split, kind, index)
    word = rng.choice(FILE_WORDS)
    line_count = rng.randint(5, 9)
    lines = []
    for number in range(1, line_count + 1):
        lines.append("line %d: %s value %d" % (number, rng.choice(FILE_WORDS),
                                               rng.randint(10, 99)))
    positions = rng.sample(range(line_count), 2)
    for position in positions:
        lines[position] = "line %d: %s appears in this line" % (position + 1, word)
    content = "\n".join(lines) + "\n"
    return {"path": path, "word": word, "content": content,
            "lines": lines, "files": {path: content}}


def _dir_case(rng: random.Random, split: str, index: int) -> Dict[str, Any]:
    directory = "%s/dir_%02d" % (split, index)
    files = {}
    txt_count = 2 + (index % 2)
    for number in range(4):
        extension = "txt" if number < txt_count else "md"
        path = "%s/file_%d.%s" % (directory, number, extension)
        files[path] = "content for file %d in %s\n" % (number, directory)
    return {"directory": directory, "files": files,
            "txt_count": txt_count, "all_files": sorted(files)}


def build_file_read(rng: random.Random, index: int, split: str) -> Dict[str, Any]:
    case = _file_case(rng, split, index, "notes")
    return dict(prompt="Read the file %s and return its exact contents." % case["path"],
                tool="file_read", arguments={"path": case["path"]},
                environment={"files": case["files"]},
                answer=lambda result: result)


def build_file_count_lines(rng: random.Random, index: int, split: str) -> Dict[str, Any]:
    case = _file_case(rng, split, index, "lines")
    return dict(prompt="How many lines are in the file %s?" % case["path"],
                tool="file_read", arguments={"path": case["path"]},
                environment={"files": case["files"]},
                answer=lambda result: len(result.splitlines()))


def build_file_search_first(rng: random.Random, index: int, split: str) -> Dict[str, Any]:
    case = _file_case(rng, split, index, "search")
    return dict(prompt="In %s, find the first line containing the word '%s'. "
                       "Return that line exactly." % (case["path"], case["word"]),
                tool="file_search",
                arguments={"path": case["path"], "pattern": case["word"]},
                environment={"files": case["files"]},
                answer=lambda result: result[0]["text"] if result else "")


def build_file_search_count(rng: random.Random, index: int, split: str) -> Dict[str, Any]:
    case = _file_case(rng, split, index, "matches")
    return dict(prompt="How many lines in %s contain the word '%s'?"
                       % (case["path"], case["word"]),
                tool="file_search",
                arguments={"path": case["path"], "pattern": case["word"]},
                environment={"files": case["files"]},
                answer=lambda result: len(result))


def build_file_write(rng: random.Random, index: int, split: str) -> Dict[str, Any]:
    path = "%s/write_%02d.txt" % (split, index)
    text = "deterministic report %02d" % index
    return dict(prompt="Write the text '%s' to %s and report how many characters "
                       "were written." % (text, path),
                tool="file_write", arguments={"path": path, "content": text},
                environment={"files": {}},
                answer=lambda result: result["characters"])


def build_file_write_test(rng: random.Random, index: int, split: str) -> Dict[str, Any]:
    path = "%s/write_%02d.txt" % (split, index)
    text = "stored message %02d" % index
    return dict(prompt="Save the sentence '%s' in %s and return the stored character count."
                       % (text, path),
                tool="file_write", arguments={"path": path, "content": text},
                environment={"files": {}},
                answer=lambda result: result["characters"])


def build_file_read_line(rng: random.Random, index: int, split: str) -> Dict[str, Any]:
    case = _file_case(rng, split, index, "indexed")
    line_no = rng.randint(1, len(case["lines"]))
    return dict(prompt="Return line %d of the file %s." % (line_no, case["path"]),
                tool="file_read", arguments={"path": case["path"]},
                environment={"files": case["files"]},
                answer=lambda result: result.splitlines()[line_no - 1])


def build_file_list_count(rng: random.Random, index: int, split: str) -> Dict[str, Any]:
    case = _dir_case(rng, split, index)
    return dict(prompt="How many .txt files are under the directory %s?"
                       % case["directory"],
                tool="file_list", arguments={"directory": case["directory"]},
                environment={"files": case["files"]},
                answer=lambda result: sum(path.endswith(".txt") for path in result))


def build_file_list_all(rng: random.Random, index: int, split: str) -> Dict[str, Any]:
    case = _dir_case(rng, split, index)
    return dict(prompt="List every file under the directory %s, recursively."
                       % case["directory"],
                tool="file_list", arguments={"directory": case["directory"]},
                environment={"files": case["files"]},
                answer=lambda result: result)


def build_file_word_count(rng: random.Random, index: int, split: str) -> Dict[str, Any]:
    case = _file_case(rng, split, index, "words")
    return dict(prompt="How many whitespace-separated words are in %s?" % case["path"],
                tool="file_read", arguments={"path": case["path"]},
                environment={"files": case["files"]},
                answer=lambda result: len(result.split()))


def build_file_last_match(rng: random.Random, index: int, split: str) -> Dict[str, Any]:
    case = _file_case(rng, split, index, "last")
    return dict(prompt="Return the last line in %s that contains the word '%s'."
                       % (case["path"], case["word"]),
                tool="file_search",
                arguments={"path": case["path"], "pattern": case["word"]},
                environment={"files": case["files"]},
                answer=lambda result: result[-1]["text"] if result else "")


# ---------------------------------------------------------------------------
# SQLite family
# ---------------------------------------------------------------------------

DB_CONTEXT = (
    "DATABASE (read-only):\n"
    "employees(id INTEGER, name TEXT, department TEXT, salary REAL, age INTEGER)\n"
    "sales(id INTEGER, product TEXT, region TEXT, amount REAL, month TEXT)\n"
    "products(id INTEGER, name TEXT, category TEXT, price REAL, stock INTEGER)"
)

DB_COLUMNS = {
    "employees": ["id", "name", "department", "salary", "age"],
    "sales": ["id", "product", "region", "amount", "month"],
    "products": ["id", "name", "category", "price", "stock"],
}
DB_NUMERIC = {
    "employees": ["salary", "age"],
    "sales": ["amount"],
    "products": ["price", "stock"],
}
DB_GROUPS = {
    "employees": "department",
    "sales": "region",
    "products": "category",
}
DB_NAMES = {
    "employees": "name",
    "sales": "product",
    "products": "name",
}
DB_STRINGS = {
    "employees": {"department": ["Engineering", "Sales", "HR", "Finance"]},
    "sales": {"region": ["North", "South", "East", "West"],
              "product": ["Widget", "Gadget", "Doohickey"]},
    "products": {"category": ["Hardware", "Software", "Accessories"]},
}

TRAIN_DB_TABLES = ["employees", "sales"]
VAL_DB_TABLES = ["products"]
TEST_DB_TABLES = ["employees", "sales", "products"]


def _quote(value: str) -> str:
    return "'%s'" % value.replace("'", "''")


def _sql_count(table: str) -> str:
    return "SELECT COUNT(*) AS n FROM %s" % table


def build_db_count(rng: random.Random, index: int, split: str) -> Dict[str, Any]:
    table = rng.choice(TRAIN_DB_TABLES if split == "train" else TEST_DB_TABLES)
    return dict(prompt="How many rows are in the %s table?" % table,
                tool="db_query", arguments={"sql": _sql_count(table)},
                environment={},
                answer=lambda result: result["rows"][0][0])


def build_db_filter_count(rng: random.Random, index: int, split: str) -> Dict[str, Any]:
    table = rng.choice(TRAIN_DB_TABLES)
    column = rng.choice(list(DB_STRINGS[table]))
    value = rng.choice(DB_STRINGS[table][column])
    sql = "SELECT COUNT(*) AS n FROM %s WHERE %s = %s" % (table, column, _quote(value))
    return dict(prompt="How many rows in %s have %s equal to '%s'?"
                       % (table, column, value),
                tool="db_query", arguments={"sql": sql}, environment={},
                answer=lambda result: result["rows"][0][0])


def build_db_average(rng: random.Random, index: int, split: str) -> Dict[str, Any]:
    table = rng.choice(TRAIN_DB_TABLES)
    column = rng.choice(DB_NUMERIC[table])
    sql = "SELECT AVG(%s) AS v FROM %s" % (column, table)
    return dict(prompt="What is the average %s in the %s table?" % (column, table),
                tool="db_query", arguments={"sql": sql}, environment={},
                answer=lambda result: result["rows"][0][0])


def build_db_group_count(rng: random.Random, index: int, split: str) -> Dict[str, Any]:
    table = rng.choice(TRAIN_DB_TABLES)
    group = DB_GROUPS[table]
    sql = ("SELECT %s, COUNT(*) AS n FROM %s GROUP BY %s ORDER BY %s"
           % (group, table, group, group))
    return dict(prompt="How many rows are in each %s group of %s? "
                       "Return a JSON object mapping each group to its count."
                       % (group, table),
                tool="db_query", arguments={"sql": sql}, environment={},
                answer=lambda result: {row[0]: row[1] for row in result["rows"]})


def build_db_top_n(rng: random.Random, index: int, split: str) -> Dict[str, Any]:
    table = rng.choice(TRAIN_DB_TABLES)
    order = rng.choice(DB_NUMERIC[table])
    name = DB_NAMES[table]
    limit = rng.randint(3, 5)
    sql = ("SELECT %s FROM %s ORDER BY %s DESC LIMIT %d"
           % (name, table, order, limit))
    return dict(prompt="List the %s values of the top %d %s rows by %s in "
                       "descending order. Return a JSON list."
                       % (name, limit, table, order),
                tool="db_query", arguments={"sql": sql}, environment={},
                answer=lambda result: [row[0] for row in result["rows"]])


def build_db_schema_count(rng: random.Random, index: int, split: str) -> Dict[str, Any]:
    if split == "train":
        tables = TRAIN_DB_TABLES
    elif split == "test":
        tables = TEST_DB_TABLES
    else:
        tables = VAL_DB_TABLES
    table = rng.choice(tables)
    return dict(prompt="How many columns does the %s table have?" % table,
                tool="db_schema", arguments={"table": table}, environment={},
                answer=lambda result: len(result))


def build_db_list_tables(rng: random.Random, index: int, split: str) -> Dict[str, Any]:
    return dict(prompt="List every table name in the database. Return a JSON list.",
                tool="db_list_tables", arguments={}, environment={},
                answer=lambda result: result)


def build_db_schema_test(rng: random.Random, index: int, split: str) -> Dict[str, Any]:
    table = rng.choice(TEST_DB_TABLES)
    return dict(prompt="How many fields does the %s table expose?" % table,
                tool="db_schema", arguments={"table": table}, environment={},
                answer=lambda result: len(result))


def build_db_list_tables_test(rng: random.Random, index: int, split: str) -> Dict[str, Any]:
    return dict(prompt="What tables are available in the read-only database? "
                       "Return a JSON list.",
                tool="db_list_tables", arguments={}, environment={},
                answer=lambda result: result)


def build_db_filter_average(rng: random.Random, index: int, split: str) -> Dict[str, Any]:
    table = rng.choice(TEST_DB_TABLES)
    value_column = rng.choice(DB_NUMERIC[table])
    filter_column = rng.choice(list(DB_STRINGS[table]))
    value = rng.choice(DB_STRINGS[table][filter_column])
    sql = ("SELECT AVG(%s) AS v FROM %s WHERE %s = %s"
           % (value_column, table, filter_column, _quote(value)))
    return dict(prompt="What is the average %s in %s for rows where %s = '%s'?"
                       % (value_column, table, filter_column, value),
                tool="db_query", arguments={"sql": sql}, environment={},
                answer=lambda result: result["rows"][0][0])


def build_db_filter_top(rng: random.Random, index: int, split: str) -> Dict[str, Any]:
    table = rng.choice(TEST_DB_TABLES)
    order = rng.choice(DB_NUMERIC[table])
    name = DB_NAMES[table]
    filter_column = rng.choice(list(DB_STRINGS[table]))
    value = rng.choice(DB_STRINGS[table][filter_column])
    limit = rng.randint(2, 4)
    sql = ("SELECT %s FROM %s WHERE %s = %s ORDER BY %s DESC LIMIT %d"
           % (name, table, filter_column, _quote(value), order, limit))
    return dict(prompt="List the %s values of the top %d %s rows by %s where "
                       "%s = '%s'. Return a JSON list."
                       % (name, limit, table, order, filter_column, value),
                tool="db_query", arguments={"sql": sql}, environment={},
                answer=lambda result: [row[0] for row in result["rows"]])


def build_db_group_average(rng: random.Random, index: int, split: str) -> Dict[str, Any]:
    table = rng.choice(TEST_DB_TABLES)
    group = DB_GROUPS[table]
    value_column = rng.choice(DB_NUMERIC[table])
    sql = ("SELECT %s, AVG(%s) AS v FROM %s GROUP BY %s ORDER BY %s"
           % (group, value_column, table, group, group))
    return dict(prompt="What is the average %s per %s in %s? Return a JSON object."
                       % (value_column, group, table),
                tool="db_query", arguments={"sql": sql}, environment={},
                answer=lambda result: {row[0]: row[1] for row in result["rows"]})


# ---------------------------------------------------------------------------
# Python statistical family
# ---------------------------------------------------------------------------

def _split_base(split: str) -> int:
    return {"train": 10, "val": 40, "test": 70}.get(split, 10)


def _stats_values(rng: random.Random, split: str, size: int = 7) -> List[int]:
    base = _split_base(split)
    values = [rng.randint(base, base + 30) for _ in range(size)]
    if len(set(values)) < 2:
        values[0] += 1
    return values


def _stats_pairs(rng: random.Random, split: str, size: int = 7):
    xs = _stats_values(rng, split, size)
    ys = [2 * x + rng.randint(-5, 5) for x in xs]
    return xs, ys


def build_stats_mean(rng: random.Random, index: int, split: str) -> Dict[str, Any]:
    values = _stats_values(rng, split)
    return dict(prompt="Compute the mean of the numbers %s." % as_json(values),
                tool="stats_mean", arguments={"values": values}, environment={},
                answer=lambda result: result)


def build_stats_median(rng: random.Random, index: int, split: str) -> Dict[str, Any]:
    values = _stats_values(rng, split)
    return dict(prompt="Compute the median of the numbers %s." % as_json(values),
                tool="stats_median", arguments={"values": values}, environment={},
                answer=lambda result: result)


def build_stats_std(rng: random.Random, index: int, split: str) -> Dict[str, Any]:
    values = _stats_values(rng, split)
    return dict(prompt="Compute the population standard deviation of the numbers %s."
                       % as_json(values),
                tool="stats_std", arguments={"values": values}, environment={},
                answer=lambda result: result)


def build_stats_percentile(rng: random.Random, index: int, split: str) -> Dict[str, Any]:
    values = _stats_values(rng, split)
    percentile = rng.choice([10, 25, 50, 75, 90])
    return dict(prompt="Compute the %dth percentile of the numbers %s."
                       % (percentile, as_json(values)),
                tool="stats_percentile",
                arguments={"values": values, "percentile": percentile},
                environment={}, answer=lambda result: result)


def build_stats_correlation(rng: random.Random, index: int, split: str) -> Dict[str, Any]:
    xs, ys = _stats_pairs(rng, split)
    return dict(prompt="Compute the Pearson correlation between xs=%s and ys=%s."
                       % (as_json(xs), as_json(ys)),
                tool="stats_correlation", arguments={"xs": xs, "ys": ys},
                environment={}, answer=lambda result: result)


def build_stats_regression(rng: random.Random, index: int, split: str) -> Dict[str, Any]:
    xs, ys = _stats_pairs(rng, split)
    return dict(prompt="Fit an ordinary least-squares line for ys on xs. Report the "
                       "slope and intercept. xs=%s ys=%s."
                       % (as_json(xs), as_json(ys)),
                tool="stats_linear_regression", arguments={"xs": xs, "ys": ys},
                environment={}, answer=lambda result: result)


def _prose(values: List[int]) -> str:
    return ", ".join(str(value) for value in values)


def build_stats_mean_prose(rng: random.Random, index: int, split: str) -> Dict[str, Any]:
    values = _stats_values(rng, split)
    return dict(prompt="The measurements are %s. What is their arithmetic average?"
                       % _prose(values),
                tool="stats_mean", arguments={"values": values}, environment={},
                answer=lambda result: result)


def build_stats_correlation_prose(rng: random.Random, index: int, split: str) -> Dict[str, Any]:
    xs, ys = _stats_pairs(rng, split)
    return dict(prompt="The first series is %s. The second series is %s. Compute the "
                       "Pearson correlation between them." % (_prose(xs), _prose(ys)),
                tool="stats_correlation", arguments={"xs": xs, "ys": ys},
                environment={}, answer=lambda result: result)


def build_stats_regression_prose(rng: random.Random, index: int, split: str) -> Dict[str, Any]:
    xs, ys = _stats_pairs(rng, split)
    pairs = ", ".join("(%d, %d)" % pair for pair in zip(xs, ys))
    return dict(prompt="The paired observations are %s. Estimate the slope and "
                       "intercept of the best-fit line." % pairs,
                tool="stats_linear_regression", arguments={"xs": xs, "ys": ys},
                environment={}, answer=lambda result: result)


def build_stats_median_prose(rng: random.Random, index: int, split: str) -> Dict[str, Any]:
    values = _stats_values(rng, split)
    return dict(prompt="The observations are %s. What is the middle value?"
                       % _prose(values),
                tool="stats_median", arguments={"values": values}, environment={},
                answer=lambda result: result)


def build_stats_std_prose(rng: random.Random, index: int, split: str) -> Dict[str, Any]:
    values = _stats_values(rng, split)
    return dict(prompt="The observations are %s. What is their population standard "
                       "deviation?" % _prose(values),
                tool="stats_std", arguments={"values": values}, environment={},
                answer=lambda result: result)


def build_stats_percentile_prose(rng: random.Random, index: int, split: str) -> Dict[str, Any]:
    values = _stats_values(rng, split)
    percentile = rng.choice([10, 25, 75, 90])
    return dict(prompt="The observations are %s. What value is at the %dth percentile?"
                       % (_prose(values), percentile),
                tool="stats_percentile",
                arguments={"values": values, "percentile": percentile},
                environment={}, answer=lambda result: result)


# ---------------------------------------------------------------------------
# Calendar family
# ---------------------------------------------------------------------------

CAL_DATES = sorted({event["date"] for event in EVENTS})
CAL_MONTHS = sorted({event["date"][:7] for event in EVENTS})
CAL_FRAGMENTS = ["Review", "Standup", "Planning", "Sync", "Call", "Interview",
                 "Training", "Retrospective", "Demo"]


def build_calendar_count_date(rng: random.Random, index: int, split: str) -> Dict[str, Any]:
    date = rng.choice(CAL_DATES)
    return dict(prompt="How many events are scheduled on %s?" % date,
                tool="calendar_list", arguments={"date": date}, environment={},
                answer=lambda result: len(result))


def build_calendar_count_month(rng: random.Random, index: int, split: str) -> Dict[str, Any]:
    month = rng.choice(CAL_MONTHS)
    return dict(prompt="How many events are in the calendar month %s?" % month,
                tool="calendar_count", arguments={"month": month}, environment={},
                answer=lambda result: result)


def build_calendar_count_month_val(rng: random.Random, index: int, split: str) -> Dict[str, Any]:
    month = rng.choice(CAL_MONTHS)
    return dict(prompt="Count all calendar entries whose month is %s." % month,
                tool="calendar_count", arguments={"month": month}, environment={},
                answer=lambda result: result)


def build_calendar_list_titles(rng: random.Random, index: int, split: str) -> Dict[str, Any]:
    date = rng.choice(CAL_DATES)
    return dict(prompt="List the titles of all events on %s, sorted alphabetically."
                       % date,
                tool="calendar_list", arguments={"date": date}, environment={},
                answer=lambda result: sorted(event["title"] for event in result))


def build_calendar_search_dates(rng: random.Random, index: int, split: str) -> Dict[str, Any]:
    fragment = rng.choice(CAL_FRAGMENTS)
    return dict(prompt="Find events whose title contains '%s' and list their dates, "
                       "sorted." % fragment,
                tool="calendar_search", arguments={"title": fragment}, environment={},
                answer=lambda result: sorted(event["date"] for event in result))


def build_calendar_search_count(rng: random.Random, index: int, split: str) -> Dict[str, Any]:
    fragment = rng.choice(CAL_FRAGMENTS)
    return dict(prompt="How many events have '%s' in their title?" % fragment,
                tool="calendar_search", arguments={"title": fragment}, environment={},
                answer=lambda result: len(result))


def build_calendar_attendees(rng: random.Random, index: int, split: str) -> Dict[str, Any]:
    event = rng.choice(EVENTS)
    return dict(prompt="List the attendees of event %s." % event["id"],
                tool="calendar_attendees",
                arguments={"event_id": event["id"]}, environment={},
                answer=lambda result: result)


def build_calendar_free_slot(rng: random.Random, index: int, split: str) -> Dict[str, Any]:
    date = rng.choice(CAL_DATES)
    duration = rng.choice([30, 60])
    return dict(prompt="Find the first free %d-minute slot on %s between 09:00 and "
                       "17:00. Return start and end." % (duration, date),
                tool="calendar_free_slots",
                arguments={"date": date, "duration_minutes": duration}, environment={},
                answer=lambda result: result[0] if result else None)


def build_calendar_list_locations(rng: random.Random, index: int, split: str) -> Dict[str, Any]:
    date = rng.choice(CAL_DATES)
    return dict(prompt="List the distinct locations of events on %s, sorted." % date,
                tool="calendar_list", arguments={"date": date}, environment={},
                answer=lambda result: sorted({event["location"] for event in result}))


def build_calendar_attendees_count(rng: random.Random, index: int, split: str) -> Dict[str, Any]:
    event = rng.choice(EVENTS)
    return dict(prompt="How many attendees does event %s have?" % event["id"],
                tool="calendar_attendees",
                arguments={"event_id": event["id"]}, environment={},
                answer=lambda result: len(result))


def build_calendar_free_slot_latest(rng: random.Random, index: int, split: str) -> Dict[str, Any]:
    date = rng.choice(CAL_DATES)
    duration = rng.choice([30, 60])
    return dict(prompt="Find the last free %d-minute slot on %s between 09:00 and "
                       "17:00. Return start and end." % (duration, date),
                tool="calendar_free_slots",
                arguments={"date": date, "duration_minutes": duration}, environment={},
                answer=lambda result: result[-1] if result else None)


# ---------------------------------------------------------------------------
# Template registry
# ---------------------------------------------------------------------------

TEMPLATES: Dict[str, List[Template]] = {
    "file": [
        Template("file_read_exact", "file", "train", ["file_read", "final_formatting"], build_file_read),
        Template("file_count_lines", "file", "train", ["file_read", "counting"], build_file_count_lines),
        Template("file_search_first", "file", "train", ["file_search", "line_index"], build_file_search_first),
        Template("file_list_count", "file", "train", ["file_list", "counting"], build_file_list_count),
        Template("file_write_report", "file", "train", ["file_write", "character_count"], build_file_write),
        Template("file_search_count", "file", "val", ["file_search", "counting"], build_file_search_count),
        Template("file_read_line", "file", "val", ["file_read", "line_index"], build_file_read_line),
        Template("file_word_count", "file", "test", ["file_read", "counting"], build_file_word_count),
        Template("file_last_match", "file", "test", ["file_search", "line_index"], build_file_last_match),
        Template("file_list_all", "file", "test", ["file_list", "final_formatting"], build_file_list_all),
        Template("file_write_test", "file", "test", ["file_write", "character_count"], build_file_write_test),
    ],
    "database": [
        Template("db_count", "database", "train", ["sql_table", "sql_count"], build_db_count),
        Template("db_filter_count", "database", "train", ["sql_filter", "sql_count"], build_db_filter_count),
        Template("db_average", "database", "train", ["sql_table", "sql_aggregation"], build_db_average),
        Template("db_group_count", "database", "train", ["sql_group", "sql_count"], build_db_group_count),
        Template("db_top_n", "database", "train", ["sql_order", "sql_select"], build_db_top_n),
        Template("db_schema_count", "database", "train", ["schema_reading", "counting"], build_db_schema_count),
        Template("db_list_tables", "database", "train", ["tool_selection", "schema_reading"], build_db_list_tables),
        Template("db_schema_count_val", "database", "val", ["schema_reading", "counting"], build_db_schema_count),
        Template("db_filter_average", "database", "test", ["sql_filter", "sql_aggregation"], build_db_filter_average),
        Template("db_filter_top", "database", "test", ["sql_filter", "sql_order"], build_db_filter_top),
        Template("db_group_average", "database", "test", ["sql_group", "sql_aggregation"], build_db_group_average),
        Template("db_schema_test", "database", "test", ["schema_reading", "counting"], build_db_schema_test),
        Template("db_list_tables_test", "database", "test", ["tool_selection", "schema_reading"], build_db_list_tables_test),
    ],
    "python": [
        Template("stats_mean", "python", "train", ["stat_mean", "numeric_input"], build_stats_mean),
        Template("stats_median", "python", "train", ["stat_median", "numeric_input"], build_stats_median),
        Template("stats_std", "python", "train", ["stat_std", "numeric_input"], build_stats_std),
        Template("stats_percentile", "python", "train", ["stat_percentile", "numeric_input"], build_stats_percentile),
        Template("stats_correlation", "python", "train", ["stat_correlation", "numeric_input"], build_stats_correlation),
        Template("stats_regression", "python", "train", ["stat_regression", "numeric_input"], build_stats_regression),
        Template("stats_median_wording", "python", "val", ["stat_median", "numeric_input"], build_stats_median),
        Template("stats_percentile_wording", "python", "val", ["stat_percentile", "numeric_input"], build_stats_percentile),
        Template("stats_mean_prose", "python", "test", ["stat_mean", "numeric_input"], build_stats_mean_prose),
        Template("stats_correlation_prose", "python", "test", ["stat_correlation", "numeric_input"], build_stats_correlation_prose),
        Template("stats_regression_prose", "python", "test", ["stat_regression", "numeric_input"], build_stats_regression_prose),
        Template("stats_median_prose", "python", "test", ["stat_median", "numeric_input"], build_stats_median_prose),
        Template("stats_std_prose", "python", "test", ["stat_std", "numeric_input"], build_stats_std_prose),
        Template("stats_percentile_prose", "python", "test", ["stat_percentile", "numeric_input"], build_stats_percentile_prose),
    ],
    "calendar": [
        Template("calendar_count_date", "calendar", "train", ["calendar_date", "calendar_count"], build_calendar_count_date),
        Template("calendar_count_month", "calendar", "train", ["calendar_month", "calendar_count"], build_calendar_count_month),
        Template("calendar_list_titles", "calendar", "train", ["calendar_list", "calendar_date"], build_calendar_list_titles),
        Template("calendar_search_dates", "calendar", "train", ["calendar_search", "calendar_date"], build_calendar_search_dates),
        Template("calendar_attendees", "calendar", "train", ["calendar_attendees", "calendar_event"], build_calendar_attendees),
        Template("calendar_free_slot", "calendar", "train", ["calendar_time", "calendar_free"], build_calendar_free_slot),
        Template("calendar_count_month_val", "calendar", "val", ["calendar_month", "calendar_count"], build_calendar_count_month_val),
        Template("calendar_search_count", "calendar", "val", ["calendar_search", "calendar_count"], build_calendar_search_count),
        Template("calendar_list_locations", "calendar", "test", ["calendar_list"], build_calendar_list_locations),
        Template("calendar_attendees_count", "calendar", "test", ["calendar_attendees", "calendar_count"], build_calendar_attendees_count),
        Template("calendar_free_slot_latest", "calendar", "test", ["calendar_time", "calendar_free"], build_calendar_free_slot_latest),
    ],
}
