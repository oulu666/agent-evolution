"""Read-only deterministic calendar tools over a local JSON fixture."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .base import ToolError, ToolRegistry, require_str

WORK_START = 9 * 60
WORK_END = 17 * 60
TITLES = ["Design Review", "Sprint Planning", "Standup", "Budget Sync",
          "Customer Call", "Interview", "Training", "Retrospective", "1:1", "Demo"]
LOCATIONS = ["Room A", "Room B", "Room C"]
ATTENDEES = ["Alice", "Bob", "Carol", "David", "Eve", "Frank",
             "Grace", "Heidi", "Ivan", "Judy"]
SLOTS = [("09:00", "10:00"), ("11:00", "12:00"),
         ("13:00", "14:00"), ("15:00", "16:00")]


def default_events() -> List[Dict[str, Any]]:
    events = []
    number = 1
    for month in (3, 4, 5):
        for day in (2, 3, 4, 5, 6):
            date = "2026-%02d-%02d" % (month, day)
            for slot_index, (start, end) in enumerate(SLOTS):
                title = TITLES[(number - 1) % len(TITLES)]
                attendees = [ATTENDEES[(number + offset) % len(ATTENDEES)]
                             for offset in range(2 + (number % 3))]
                events.append({
                    "id": "E%03d" % number,
                    "title": title,
                    "date": date,
                    "start": start,
                    "end": end,
                    "location": LOCATIONS[number % len(LOCATIONS)],
                    "attendees": attendees,
                })
                number += 1
    return events


EVENTS = default_events()


def create_calendar_fixture(path: str, force: bool = False) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if force or not target.exists():
        target.write_text(json.dumps({"events": EVENTS}, ensure_ascii=False, indent=2),
                          encoding="utf-8")
    return target


def _minutes(value: str) -> int:
    match = re.fullmatch(r"(\d{2}):(\d{2})", value)
    if not match:
        raise ToolError("time must be HH:MM")
    hour, minute = int(match.group(1)), int(match.group(2))
    if hour > 23 or minute > 59:
        raise ToolError("invalid time")
    return hour * 60 + minute


def _clock(minutes: int) -> str:
    return "%02d:%02d" % (minutes // 60, minutes % 60)


class CalendarStore:
    def __init__(self, path: str) -> None:
        target = Path(path)
        if not target.exists():
            raise ToolError("calendar fixture not found")
        data = json.loads(target.read_text(encoding="utf-8"))
        self.events = data.get("events", [])
        if not isinstance(self.events, list):
            raise ToolError("calendar fixture is malformed")

    def list_date(self, date: str) -> List[Dict[str, Any]]:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            raise ToolError("date must be YYYY-MM-DD")
        events = [event for event in self.events if event["date"] == date]
        return sorted(events, key=lambda event: (event["start"], event["id"]))

    def search(self, title: str) -> List[Dict[str, Any]]:
        needle = title.casefold()
        events = [event for event in self.events if needle in event["title"].casefold()]
        return sorted(events, key=lambda event: (event["date"], event["start"], event["id"]))

    def count_month(self, month: str) -> int:
        if not re.fullmatch(r"\d{4}-\d{2}", month):
            raise ToolError("month must be YYYY-MM")
        return sum(1 for event in self.events if event["date"].startswith(month + "-"))

    def free_slots(self, date: str, duration_minutes: int) -> List[Dict[str, str]]:
        if duration_minutes < 15 or duration_minutes > 240:
            raise ToolError("duration_minutes must be between 15 and 240")
        events = self.list_date(date)
        busy: List[Tuple[int, int]] = []
        for event in events:
            busy.append((_minutes(event["start"]), _minutes(event["end"])))
        busy.sort()
        merged: List[Tuple[int, int]] = []
        for start, end in busy:
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        slots = []
        cursor = WORK_START
        for start, end in merged:
            if start > cursor and start - cursor >= duration_minutes:
                slots.append({"start": _clock(cursor), "end": _clock(start)})
            cursor = max(cursor, end)
        if WORK_END - cursor >= duration_minutes:
            slots.append({"start": _clock(cursor), "end": _clock(WORK_END)})
        return slots

    def attendees(self, event_id: str) -> List[str]:
        for event in self.events:
            if event["id"] == event_id:
                return list(event["attendees"])
        raise ToolError("unknown event id: %s" % event_id)


def build_calendar_registry(path: str) -> ToolRegistry:
    store = CalendarStore(path)
    registry = ToolRegistry()
    registry.register(
        "calendar_list",
        "List the events on one date, sorted by start time.",
        {"type": "object", "properties": {"date": {"type": "string"}},
         "required": ["date"], "additionalProperties": False},
        lambda args: store.list_date(require_str(args, "date")),
    )
    registry.register(
        "calendar_search",
        "Find events whose title contains a case-insensitive substring.",
        {"type": "object", "properties": {"title": {"type": "string"}},
         "required": ["title"], "additionalProperties": False},
        lambda args: store.search(require_str(args, "title")),
    )
    registry.register(
        "calendar_count",
        "Count events in a month given as YYYY-MM.",
        {"type": "object", "properties": {"month": {"type": "string"}},
         "required": ["month"], "additionalProperties": False},
        lambda args: store.count_month(require_str(args, "month")),
    )
    registry.register(
        "calendar_free_slots",
        "List free workday slots (09:00-17:00) of at least a given duration.",
        {"type": "object",
         "properties": {"date": {"type": "string"},
                        "duration_minutes": {"type": "integer"}},
         "required": ["date", "duration_minutes"], "additionalProperties": False},
        lambda args: store.free_slots(
            require_str(args, "date"),
            int(args.get("duration_minutes", -1))
            if isinstance(args.get("duration_minutes"), int) else -1),
    )
    registry.register(
        "calendar_attendees",
        "Return the attendee list of one event id.",
        {"type": "object", "properties": {"event_id": {"type": "string"}},
         "required": ["event_id"], "additionalProperties": False},
        lambda args: store.attendees(require_str(args, "event_id")),
    )
    return registry
