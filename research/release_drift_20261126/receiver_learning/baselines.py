"""Baselines that do not localize a slot from demonstrations.

Indices are the harness vector positions passed as `receiver` at 7a2971af.
The copy harness labels those positions title, clipboard, page code after scoring.
The jq harness labels them stderr, input, destination, stdout.
"""

LOOKUP = {
    "material-copy-button": 1,
    "jq-stdout": 3,
    "jq-file-redirect": 2,
}

METHODS = (
    "learned",
    "after_only",
    "lookup",
    "fixed_replay",
    "all_readable_all_match",
    "all_readable_any_match",
)


def lookup_positions(action):
    if action not in LOOKUP:
        return []
    return [LOOKUP[action]]


def metrics(rows):
    """Count releases against the labeled receiver. Deferral is neither release nor block."""
    out = {}
    violations = [row for row in rows if row["truth"] is False]
    healthy = [row for row in rows if row["truth"] is True]
    for method in METHODS:
        def count(subset, value, method=method):
            return sum(row["decisions"][method] is value for row in subset)
        out[method] = {
            "violation_rows": len(violations),
            "healthy_rows": len(healthy),
            "false_release": count(violations, True),
            "correct_block": count(violations, False),
            "violation_deferred": count(violations, None),
            "retention": count(healthy, True),
            "false_block": count(healthy, False),
            "healthy_deferred": count(healthy, None),
        }
    return out
