"""Operation-pattern catalog and read-only classifiers for Coverage Estimator.

This module does not invent a skill tree. Patterns are clustered from the
existing template_id values and from the actual tool + argument / SQL
structures in data_phase2, data_ext_e4, data_ext_cal_v3, and the P0 exams.

Official classification prefers template_id (via TEMPLATE_TO_PATTERN).
Structural fallback is used only when template_id is missing or unknown,
and may return an *.unknown code rather than guess.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Official catalog
# ---------------------------------------------------------------------------

# (pattern_id, tool_family, short description)
CATALOG: Tuple[Tuple[str, str, str], ...] = (
    # Database
    ("db.list_tables", "database", "调用 db_list_tables，列出全部表名"),
    ("db.schema_count", "database", "调用 db_schema，回答某表有多少列"),
    ("db.count_all", "database", "SELECT COUNT(*)，无 WHERE"),
    ("db.filter_eq_count", "database", "COUNT(*) + WHERE 字符串等值"),
    ("db.filter_cmp_count", "database", "COUNT(*) + WHERE 数值比较"),
    ("db.avg_all", "database", "SELECT AVG(col)，无 WHERE"),
    ("db.filter_eq_avg", "database", "AVG + WHERE 字符串等值"),
    ("db.filter_cmp_avg", "database", "AVG + WHERE 数值比较"),
    ("db.group_count", "database", "GROUP BY + COUNT，无数值预过滤"),
    ("db.group_avg", "database", "GROUP BY + AVG"),
    ("db.filter_cmp_group_count", "database", "WHERE 数值比较后再 GROUP BY + COUNT"),
    ("db.top_n", "database", "ORDER BY + LIMIT，无 WHERE"),
    ("db.filter_eq_top", "database", "WHERE 字符串等值 + ORDER BY + LIMIT"),
    ("db.filter_cmp_top", "database", "WHERE 数值比较 + ORDER BY + LIMIT（可带次级排序）"),
    ("db.min_max", "database", "MIN/MAX，可带可选的数值过滤"),
    ("db.multi_filter_count", "database", "COUNT(*) + 字符串等值 AND 数值比较"),
    # File
    ("file.read_exact", "file", "file_read，返回文件原文"),
    ("file.count_lines", "file", "file_read，统计行数"),
    ("file.word_count", "file", "file_read，统计空白分词后的词数"),
    ("file.search_first", "file", "file_search，取第一次匹配的行"),
    ("file.search_last", "file", "file_search，取最后一次匹配的行"),
    ("file.list_count", "file", "file_list，统计目录下 .txt 文件数"),
    ("file.list_all", "file", "file_list，递归列出全部文件"),
    ("file.write_char_count", "file", "file_write，返回写入的字符数"),
    # Python / stats tools
    ("py.mean", "python", "调用 stats_mean"),
    ("py.median", "python", "调用 stats_median"),
    ("py.std", "python", "调用 stats_std"),
    ("py.percentile", "python", "调用 stats_percentile"),
    ("py.correlation", "python", "调用 stats_correlation"),
    ("py.regression", "python", "调用 stats_linear_regression"),
    # Calendar
    ("cal.count_date", "calendar", "calendar_list(date)，清点当天全部事件数"),
    ("cal.count_month", "calendar", "calendar_count(month)，按月计数"),
    ("cal.list_titles", "calendar", "calendar_list(date)，按字母序列出标题"),
    ("cal.list_locations", "calendar", "calendar_list(date)，去重并列地点"),
    ("cal.last_end", "calendar", "calendar_list(date)，取当天最后一场的结束时间"),
    ("cal.day_title_count", "calendar", "calendar_list(date)，清点标题含某片段的事件数"),
    ("cal.search_dates", "calendar", "calendar_search(title)，列出命中日期"),
    ("cal.search_count", "calendar", "calendar_search(title)，清点命中条数"),
    ("cal.attendees_list", "calendar", "calendar_attendees(event_id)，列出出席者"),
    ("cal.attendees_count", "calendar", "calendar_attendees(event_id)，清点出席人数"),
    ("cal.free_first", "calendar", "calendar_free_slots，取当天第一段空闲"),
    ("cal.free_latest", "calendar", "calendar_free_slots，取当天最后一段空闲"),
)

OFFICIAL_PATTERNS: Tuple[str, ...] = tuple(p[0] for p in CATALOG)
PATTERN_FAMILY: Dict[str, str] = {p: f for p, f, _ in CATALOG}
PATTERN_DESC: Dict[str, str] = {p: d for p, _, d in CATALOG}

# Known template_id → official pattern. This is the primary, reproducible rule.
TEMPLATE_TO_PATTERN: Dict[str, str] = {
    # Database train / test / targets / P0 nontarget
    "db_list_tables": "db.list_tables",
    "db_list_tables_test": "db.list_tables",
    "db_schema_count": "db.schema_count",
    "db_schema_test": "db.schema_count",
    "db_count": "db.count_all",
    "db_filter_count": "db.filter_eq_count",
    "nontarget_filter_count": "db.filter_cmp_count",
    "db_average": "db.avg_all",
    "db_filter_average": "db.filter_eq_avg",
    "nontarget_filter_mean": "db.filter_cmp_avg",
    "db_group_count": "db.group_count",
    "db_group_average": "db.group_avg",
    "nontarget_group_count_filter": "db.filter_cmp_group_count",
    "db_top_n": "db.top_n",
    "db_filter_top": "db.filter_eq_top",
    "target_db_filter_top": "db.filter_cmp_top",
    "nontarget_min_max": "db.min_max",
    "nontarget_multi_filter_count": "db.multi_filter_count",
    # File
    "file_read_exact": "file.read_exact",
    "file_count_lines": "file.count_lines",
    "file_word_count": "file.word_count",
    "file_search_first": "file.search_first",
    "file_last_match": "file.search_last",
    "target_file_last_match": "file.search_last",
    "e4_target_file_last_match": "file.search_last",
    "file_list_count": "file.list_count",
    "file_list_all": "file.list_all",
    "file_write_report": "file.write_char_count",
    "file_write_test": "file.write_char_count",
    # Python (prose / natural wording are the same operation)
    "stats_mean": "py.mean",
    "stats_mean_prose": "py.mean",
    "stats_median": "py.median",
    "stats_median_prose": "py.median",
    "target_median_natural": "py.median",
    "stats_std": "py.std",
    "stats_std_prose": "py.std",
    "stats_percentile": "py.percentile",
    "stats_percentile_prose": "py.percentile",
    "stats_correlation": "py.correlation",
    "stats_correlation_prose": "py.correlation",
    "stats_regression": "py.regression",
    "stats_regression_prose": "py.regression",
    # Calendar train / phase2 test / nat v2 / v3 / v3fix
    "calendar_count_date": "cal.count_date",
    "nf2_cal_nl_count_date": "cal.count_date",
    "calendar_count_month": "cal.count_month",
    "nf2_cal_nl_count_month": "cal.count_month",
    "calendar_list_titles": "cal.list_titles",
    "nf2_cal_nl_list_titles": "cal.list_titles",
    "calendar_list_locations": "cal.list_locations",
    "cv3_locations": "cal.list_locations",
    "calendar_search_dates": "cal.search_dates",
    "nf2_cal_nl_search_dates": "cal.search_dates",
    "cv3_search_count": "cal.search_count",
    "calendar_attendees": "cal.attendees_list",
    "nf2_cal_nl_attendees": "cal.attendees_list",
    "calendar_attendees_count": "cal.attendees_count",
    "cv3_attendee_count": "cal.attendees_count",
    "calendar_free_slot": "cal.free_first",
    "nf2_cal_nl_free_first": "cal.free_first",
    "calendar_free_slot_latest": "cal.free_latest",
    "cv3_free_latest": "cal.free_latest",
    "cv3_last_end": "cal.last_end",
    "cv3fix_day_count": "cal.day_title_count",
}

# Tool name used by python / calendar structural fallback.
TOOL_TO_PATTERN: Dict[str, str] = {
    "db_list_tables": "db.list_tables",
    "db_schema": "db.schema_count",
    "stats_mean": "py.mean",
    "stats_median": "py.median",
    "stats_std": "py.std",
    "stats_percentile": "py.percentile",
    "stats_correlation": "py.correlation",
    "stats_linear_regression": "py.regression",
    "calendar_count": "cal.count_month",
}

UNKNOWN_PREFIX = {
    "database": "db.unknown",
    "file": "file.unknown",
    "python": "py.unknown",
    "calendar": "cal.unknown",
}


@dataclass
class Classification:
    pattern: str
    source: str  # "template_id" | "structural" | "unknown"
    official: bool
    template_id: Optional[str] = None
    expected_tool: Optional[str] = None
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# SQL / argument features
# ---------------------------------------------------------------------------

_RE_WHERE = re.compile(r"\bWHERE\b", re.I)
_RE_GROUP = re.compile(r"\bGROUP\s+BY\b", re.I)
_RE_ORDER = re.compile(r"\bORDER\s+BY\b", re.I)
_RE_LIMIT = re.compile(r"\bLIMIT\b", re.I)
_RE_COUNT = re.compile(r"\bCOUNT\s*\(", re.I)
_RE_AVG = re.compile(r"\bAVG\s*\(", re.I)
_RE_MIN = re.compile(r"\bMIN\s*\(", re.I)
_RE_MAX = re.compile(r"\bMAX\s*\(", re.I)
_RE_AND = re.compile(r"\bAND\b", re.I)
# Numeric / inequality predicate in WHERE. Keep '=' out of this class.
_RE_CMP = re.compile(
    r"(?:<>|<=|>=|!=|>|<)\s*(?:\d|\')|(?:\d)\s*(?:<>|<=|>=|!=|>|<)",
    re.I,
)
# String or identifier equality. Best-effort; not a full SQL parser.
_RE_EQ = re.compile(r"(?<!<|>|!)=(?!=)")


def sql_features(sql: str) -> Dict[str, bool]:
    text = " ".join((sql or "").split())
    where = ""
    m = _RE_WHERE.search(text)
    if m:
        tail = text[m.end():]
        cut = _RE_GROUP.search(tail) or _RE_ORDER.search(tail)
        where = tail[: cut.start()] if cut else tail
    return {
        "where": bool(m),
        "group": bool(_RE_GROUP.search(text)),
        "order": bool(_RE_ORDER.search(text)),
        "limit": bool(_RE_LIMIT.search(text)),
        "count": bool(_RE_COUNT.search(text)),
        "avg": bool(_RE_AVG.search(text)),
        "min": bool(_RE_MIN.search(text)),
        "max": bool(_RE_MAX.search(text)),
        "and": bool(_RE_AND.search(where)),
        "cmp": bool(_RE_CMP.search(where)),
        "eq": bool(_RE_EQ.search(where)),
    }


def first_user_text(row: Mapping[str, Any]) -> str:
    if row.get("prompt"):
        return str(row["prompt"])
    for msg in row.get("messages") or []:
        if msg.get("role") != "user":
            continue
        content = msg.get("content") or ""
        if isinstance(content, list):
            content = " ".join(str(x) for x in content)
        if not str(content).startswith("TOOL RESULT"):
            return str(content)
    return ""


def experience_identity(row: Mapping[str, Any]) -> str:
    """Stable identity of one experience / exam item.

    Prefer episode_id. If missing, hash tool + arguments + prompt.
    Repeats of the same episode_id count as the same identity.
    """
    eid = row.get("episode_id")
    if eid:
        return str(eid)
    payload = {
        "template_id": row.get("template_id"),
        "expected_tool": row.get("expected_tool"),
        "expected_arguments": row.get("expected_arguments"),
        "prompt": first_user_text(row),
    }
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return "hash:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def _unknown(family: Optional[str], reason: str, **extra: Any) -> Classification:
    code = UNKNOWN_PREFIX.get(family or "", "unknown")
    return Classification(pattern=code, source="unknown", official=False, notes=reason, **extra)


def classify_sql_query(sql: str) -> Optional[str]:
    """Map a db_query SQL string to a pattern, or None if it does not fit."""
    f = sql_features(sql)
    if f["min"] or f["max"]:
        return "db.min_max"
    if f["group"] and f["count"] and f["where"] and f["cmp"]:
        return "db.filter_cmp_group_count"
    if f["group"] and f["count"]:
        return "db.group_count"
    if f["group"] and f["avg"]:
        return "db.group_avg"
    if f["order"] and f["limit"] and f["where"] and f["cmp"]:
        return "db.filter_cmp_top"
    if f["order"] and f["limit"] and f["where"]:
        return "db.filter_eq_top"
    if f["order"] and f["limit"]:
        return "db.top_n"
    if f["count"] and f["where"] and f["and"] and f["eq"] and f["cmp"]:
        return "db.multi_filter_count"
    if f["count"] and f["where"] and f["cmp"]:
        return "db.filter_cmp_count"
    if f["count"] and f["where"]:
        return "db.filter_eq_count"
    if f["count"]:
        return "db.count_all"
    if f["avg"] and f["where"] and f["cmp"]:
        return "db.filter_cmp_avg"
    if f["avg"] and f["where"]:
        return "db.filter_eq_avg"
    if f["avg"]:
        return "db.avg_all"
    return None


def classify_structural(row: Mapping[str, Any]) -> Classification:
    """Best-effort structural fallback. Does not invent patterns beyond the catalog.

    Some File / Calendar items share the same tool and argument keys and can
    only be disambiguated by template_id, answer_spec, or the prompt. If those
    cues are missing, this returns *.unknown rather than guessing.
    """
    tool = row.get("expected_tool")
    family = row.get("tool_family")
    args = row.get("expected_arguments") or {}
    spec = row.get("answer_spec") or {}
    prompt = first_user_text(row)
    pl = prompt.lower()

    if tool in TOOL_TO_PATTERN:
        pat = TOOL_TO_PATTERN[tool]
        return Classification(pat, "structural", pat in OFFICIAL_PATTERNS,
                              expected_tool=tool)

    if tool == "db_query":
        sql = args.get("sql") if isinstance(args, dict) else None
        if sql:
            pat = classify_sql_query(sql)
            if pat:
                return Classification(pat, "structural", True, expected_tool=tool)
        return _unknown(family or "database", "unrecognized db_query SQL", expected_tool=tool)

    if tool == "file_search":
        idx = spec.get("index") if isinstance(spec, dict) else None
        if idx == -1 or "last line" in pl or "last match" in pl or "最后" in prompt:
            return Classification("file.search_last", "structural", True, expected_tool=tool)
        if idx == 0 or "first line" in pl or "first" in pl or "第一" in prompt:
            return Classification("file.search_first", "structural", True, expected_tool=tool)
        return _unknown("file", "file_search without first/last cue", expected_tool=tool)

    if tool == "file_read":
        if "whitespace-separated words" in pl or ("how many" in pl and "word" in pl):
            return Classification("file.word_count", "structural", True, expected_tool=tool)
        if "how many lines" in pl or "line count" in pl or "多少行" in prompt:
            return Classification("file.count_lines", "structural", True, expected_tool=tool)
        if "exact contents" in pl or "return its exact" in pl:
            return Classification("file.read_exact", "structural", True, expected_tool=tool)
        return _unknown("file", "file_read without count/exact cue", expected_tool=tool)

    if tool == "file_list":
        if "how many" in pl and ".txt" in pl:
            return Classification("file.list_count", "structural", True, expected_tool=tool)
        if "list every" in pl or "recursively" in pl:
            return Classification("file.list_all", "structural", True, expected_tool=tool)
        return _unknown("file", "file_list without count/list-all cue", expected_tool=tool)

    if tool == "file_write":
        return Classification("file.write_char_count", "structural", True, expected_tool=tool)

    if tool == "calendar_list":
        kind = spec.get("kind") if isinstance(spec, dict) else None
        field = spec.get("field") if isinstance(spec, dict) else None
        if "location" in pl or field == "location" or "rooms or places" in pl:
            return Classification("cal.list_locations", "structural", True, expected_tool=tool)
        if "title containing" in pl or "have a title containing" in pl or "标题" in prompt and "含" in prompt:
            return Classification("cal.day_title_count", "structural", True, expected_tool=tool)
        if "last meeting" in pl or "finish" in pl or kind == "last_end" or "最后一场" in prompt or "end time" in pl:
            return Classification("cal.last_end", "structural", True, expected_tool=tool)
        if "titles" in pl or "names" in pl or field == "title" or "alphabet" in pl:
            return Classification("cal.list_titles", "structural", True, expected_tool=tool)
        if "how many" in pl or "how many events" in pl or "how many meetings" in pl:
            return Classification("cal.count_date", "structural", True, expected_tool=tool)
        return _unknown("calendar", "calendar_list without projection cue", expected_tool=tool)

    if tool == "calendar_search":
        kind = spec.get("kind") if isinstance(spec, dict) else None
        if kind == "length" or ("how many" in pl and "title" in pl):
            return Classification("cal.search_count", "structural", True, expected_tool=tool)
        if "dates" in pl or "on which days" in pl or (isinstance(spec, dict) and spec.get("field") == "date"):
            return Classification("cal.search_dates", "structural", True, expected_tool=tool)
        return _unknown("calendar", "calendar_search without dates/count cue", expected_tool=tool)

    if tool == "calendar_attendees":
        if "how many" in pl or "how many people" in pl or "how many attendees" in pl:
            return Classification("cal.attendees_count", "structural", True, expected_tool=tool)
        if "who is attending" in pl or "list the attendees" in pl or "attendee names" in pl:
            return Classification("cal.attendees_list", "structural", True, expected_tool=tool)
        return _unknown("calendar", "calendar_attendees without list/count cue", expected_tool=tool)

    if tool == "calendar_free_slots":
        idx = spec.get("index") if isinstance(spec, dict) else None
        if idx == -1 or "last free" in pl or "as late as possible" in pl or "最后" in prompt:
            return Classification("cal.free_latest", "structural", True, expected_tool=tool)
        if idx == 0 or "first free" in pl or "earliest" in pl or "第一" in prompt:
            return Classification("cal.free_first", "structural", True, expected_tool=tool)
        return _unknown("calendar", "calendar_free_slots without first/last cue", expected_tool=tool)

    return _unknown(family, "no structural rule for tool=%s" % tool, expected_tool=tool)


def classify_item(row: Mapping[str, Any]) -> Classification:
    tid = row.get("template_id")
    tool = row.get("expected_tool")
    if tid in TEMPLATE_TO_PATTERN:
        pat = TEMPLATE_TO_PATTERN[tid]
        return Classification(
            pattern=pat,
            source="template_id",
            official=pat in OFFICIAL_PATTERNS,
            template_id=tid,
            expected_tool=tool,
        )
    result = classify_structural(row)
    result.template_id = tid
    result.expected_tool = tool or result.expected_tool
    if tid:
        result.notes = (result.notes + "; " if result.notes else "") + "unmapped template_id=%s" % tid
    return result


# ---------------------------------------------------------------------------
# Metrics: Pattern Coverage, Experience Diversity, Skill Deficit
# ---------------------------------------------------------------------------

@dataclass
class PatternCount:
    pattern: str
    unique: int
    slots: int
    covered: bool


@dataclass
class CoverageReport:
    """Pattern Coverage = what the experience pool contains (not what the model can do)."""
    n_slots: int
    n_unique: int
    n_official_covered: int
    n_official: int
    coverage: Optional[float]  # n_official_covered / |P|
    by_pattern: Dict[str, PatternCount]
    unofficial: Dict[str, int]
    notes: str = (
        "Pattern Coverage is a property of the experience pool. "
        "It is not a model skill score and must not be substituted for Skill Deficit."
    )

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["by_pattern"] = {k: asdict(v) for k, v in self.by_pattern.items()}
        return d


def pattern_coverage(
    rows: Sequence[Mapping[str, Any]],
    catalog: Sequence[str] = OFFICIAL_PATTERNS,
) -> CoverageReport:
    slots: Dict[str, List[str]] = defaultdict(list)
    unofficial: Counter = Counter()
    for row in rows:
        c = classify_item(row)
        ident = experience_identity(row)
        if c.pattern in catalog:
            slots[c.pattern].append(ident)
        else:
            unofficial[c.pattern] += 1
            slots.setdefault(c.pattern, []).append(ident)
    by: Dict[str, PatternCount] = {}
    covered = 0
    for pat in catalog:
        ids = slots.get(pat, [])
        uniq = len(set(ids))
        rec = PatternCount(pattern=pat, unique=uniq, slots=len(ids), covered=uniq >= 1)
        by[pat] = rec
        if rec.covered:
            covered += 1
    n_slots = len(rows)
    n_unique = len({experience_identity(r) for r in rows})
    cov = (covered / len(catalog)) if catalog else None
    return CoverageReport(
        n_slots=n_slots,
        n_unique=n_unique,
        n_official_covered=covered,
        n_official=len(catalog),
        coverage=cov,
        by_pattern=by,
        unofficial=dict(unofficial),
    )


@dataclass
class DiversityReport:
    """Experience Diversity = whether slots are unique experiences, not just which patterns appear."""
    n_slots: int
    n_unique: int
    uniqueness: Optional[float]          # |unique ids| / |slots|
    pattern_entropy: Optional[float]     # Shannon entropy of slot pattern distribution (nats)
    max_entropy: Optional[float]         # ln(n_present_patterns)
    normalized_entropy: Optional[float]  # entropy / max_entropy
    within_pattern: Dict[str, Dict[str, Any]]
    notes: str = (
        "High uniqueness on a single pattern is not high Pattern Coverage. "
        "High pattern entropy on a small subset of the catalog is not high Coverage. "
        "Repeating one valuable identity is a diversity fact, not a coverage fact."
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _entropy(counts: Sequence[int]) -> Optional[float]:
    total = sum(counts)
    if total <= 0:
        return None
    h = 0.0
    for c in counts:
        if c <= 0:
            continue
        p = c / total
        h -= p * (p and __import__("math").log(p))
    return h


def experience_diversity(rows: Sequence[Mapping[str, Any]]) -> DiversityReport:
    import math
    n = len(rows)
    ids = [experience_identity(r) for r in rows]
    n_unique = len(set(ids))
    uniqueness = (n_unique / n) if n else None
    by_pat: Dict[str, List[str]] = defaultdict(list)
    arg_sigs: Dict[str, set] = defaultdict(set)
    for row in rows:
        pat = classify_item(row).pattern
        ident = experience_identity(row)
        by_pat[pat].append(ident)
        args = row.get("expected_arguments")
        arg_sigs[pat].add(json.dumps(args, ensure_ascii=False, sort_keys=True, default=str))
    slot_counts = [len(v) for v in by_pat.values()]
    h = _entropy(slot_counts)
    k = len([c for c in slot_counts if c > 0])
    max_h = math.log(k) if k > 1 else (0.0 if k == 1 else None)
    norm = (h / max_h) if (h is not None and max_h) else (1.0 if max_h == 0.0 and h == 0.0 else None)
    within = {}
    for pat, idlist in sorted(by_pat.items()):
        u = len(set(idlist))
        within[pat] = {
            "slots": len(idlist),
            "unique_ids": u,
            "uniqueness": u / len(idlist) if idlist else None,
            "unique_arg_signatures": len(arg_sigs[pat]),
        }
    return DiversityReport(
        n_slots=n,
        n_unique=n_unique,
        uniqueness=uniqueness,
        pattern_entropy=h,
        max_entropy=max_h,
        normalized_entropy=norm,
        within_pattern=within,
    )


def skill_from_results(
    results: Sequence[Mapping[str, Any]],
    success_field: str = "joint_success",
    fallback_field: str = "final_correct",
    tool_field: str = "tool_correct",
) -> Dict[str, Any]:
    """Compute Skill / Deficit on an already scored result list (one pattern or mixed).

    This is a Skill / Forgetting Monitor quantity: it describes the model, not the pool.
    Protocol (batch size, exam identity) must be recorded by the caller; this function
    only aggregates the provided rows.
    """
    def _ok(row: Mapping[str, Any]) -> Optional[int]:
        if success_field in row and row[success_field] is not None:
            return int(bool(row[success_field]))
        if fallback_field in row and row[fallback_field] is not None:
            return int(bool(row[fallback_field]))
        return None

    flags = [_ok(r) for r in results]
    used = [x for x in flags if x is not None]
    tool = [int(bool(r[tool_field])) for r in results if r.get(tool_field) is not None]
    # Conditional counting / answer accuracy given correct tool.
    cond = []
    for r in results:
        if r.get(tool_field) is None:
            continue
        if not r.get(tool_field):
            continue
        v = _ok(r)
        if v is not None:
            cond.append(v)
    n = len(used)
    skill = (sum(used) / n) if n else None
    tool_acc = (sum(tool) / len(tool)) if tool else None
    cond_acc = (sum(cond) / len(cond)) if cond else None
    return {
        "n": n,
        "n_missing_score": len(flags) - n,
        "skill": skill,
        "deficit": (None if skill is None else 1.0 - skill),
        "tool_accuracy": tool_acc,
        "conditional_success": cond_acc,
        "success_field_used": success_field if any(r.get(success_field) is not None for r in results) else fallback_field,
        "notes": (
            "Skill Deficit is a property of a checkpoint on a named exam and protocol. "
            "Do not infer it from Pattern Coverage. Use 'forgetting' only when a T0 "
            "score exists on the same exam and protocol."
        ),
    }


def forgetting_and_recovery(
    skill_t0: Optional[float],
    skill_t1: Optional[float],
    skill_t2: Optional[float],
) -> Dict[str, Any]:
    """Named stage contrast. Returns None fields when a stage is missing.

    drop = Skill(T0) - Skill(T1); recovery = Skill(T2) - Skill(T1).
    'forgetting' may be used only if skill_t0 is not None.
    """
    drop = None if (skill_t0 is None or skill_t1 is None) else skill_t0 - skill_t1
    rec = None if (skill_t2 is None or skill_t1 is None) else skill_t2 - skill_t1
    return {
        "skill_t0": skill_t0,
        "skill_t1": skill_t1,
        "skill_t2": skill_t2,
        "drop_t0_t1": drop,
        "recovery_t1_t2": rec,
        "may_use_forgetting_term": skill_t0 is not None,
    }
