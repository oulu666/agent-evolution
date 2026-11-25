"""Frozen task and probe menus. The requested argument is supplied by the caller."""
from datetime import date

VALUES = {
    "week": ["2017-06-14", "2018-09-12", "2022-04-20", "2023-08-16",
             "2010-01-01", "2016-01-02", "2019-12-30", "2021-01-03"],
    "duration": [2.25, 7.5, 15.25, 28.5, 61.25, 74.5, 95.25, 130.5],
}
PROBES = {"week": ["2014-07-16", "2011-01-01"], "duration": [3.5, 90.25]}
TOOLS = ("week", "duration")
SCOPES = ("ordinary", "boundary")
HISTORIES = ("no_assertion", "coarse", "other_path", "supported")


def request(tool, value):
    if tool == "week":
        return f"Return the German ISO week-date label for {value} in YYYY-Www-e format."
    return f"Create a spreadsheet duration cell showing total hours for an elapsed period of {value} days."


def truth(tool, value):
    if tool == "week":
        iso = date.fromisoformat(value).isocalendar()
        return f"{iso.year:04d}-W{iso.week:02d}-{iso.weekday}"
    return float(value)

