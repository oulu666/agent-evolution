"""Synthetic checks for the frozen selection rules, labels, and decision."""

from __future__ import annotations

import ast
import hashlib
import tempfile
import textwrap
import unittest
from pathlib import Path

from outcomes import (
    EXAMINE_CAP,
    EXTRACTORS,
    INCLUDE_CAP,
    MIN_INCLUDED,
    MIN_LIBRARIES,
    NOT_RUN,
    build_driver,
    decide,
    pair_label,
    score_grounded,
    score_human,
    score_translated,
    sentence_matches,
)
from selection import (
    POOL,
    SelectionState,
    candidates_in_source,
    collect_tree,
    examine,
    judge,
    linguistic,
    parse_condition,
    propose,
)


HERE = Path(__file__).resolve().parent


def _proposal(sentence, parameters=("n",), required=("n",), posonly=()):
    return propose(sentence, list(parameters), list(required), list(posonly))


def _candidate(sentence, name="alpha", library="click", required=("n",), parameters=("n",), source=None):
    docstring = sentence if sentence.endswith(".") else sentence + "."
    # Keep the docstring identical to the sentence the splitter will see.
    text = docstring
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return {
        "library": library,
        "pypi": library,
        "version": "0",
        "import_name": "click" if library == "click" else library,
        "module": library,
        "qualname": f"{library}.{name}",
        "attrs": [name],
        "path": f"{library}/{name}.py",
        "file_sha256": digest,
        "sentence": text,
        "docstring": text,
        "doc_source": "function",
        "parameters": list(parameters),
        "required": list(required),
        "posonly": [],
        "source": text,
    }


class PatternTests(unittest.TestCase):
    def test_condition_table(self):
        self.assertEqual(parse_condition("is negative"), (-1, 0))
        self.assertEqual(parse_condition("is not negative"), (0, -1))
        self.assertEqual(parse_condition("is positive"), (1, 0))
        self.assertEqual(parse_condition("is greater than or equal to 5"), (5, 4))
        self.assertEqual(parse_condition("is less than 0"), (-1, 0))
        self.assertEqual(parse_condition("< 0"), (-1, 0))
        self.assertEqual(parse_condition(">= 0"), (0, -1))
        self.assertEqual(parse_condition("is even"), (0, 1))
        self.assertEqual(parse_condition("is zero"), (0, 1))
        self.assertIsNone(parse_condition("is none"))
        self.assertIsNone(parse_condition("is negative or zero"))

    def test_raise_inputs_are_valid_then_invalid(self):
        found = _proposal("Raises ValueError if n is negative.")
        self.assertTrue(found["ok"])
        self.assertEqual(found["pattern"], "raise_if")
        self.assertEqual(found["legal"], 0)
        self.assertEqual(found["violating"], -1)
        self.assertEqual(found["human"], {"op": "raises", "type": "ValueError"})

    def test_leading_if_and_passive_raise(self):
        lead = _proposal("If n is negative, raise ValueError.")
        passive = _proposal("A ValueError is raised if n is negative.")
        self.assertEqual((lead["legal"], lead["violating"]), (0, -1))
        self.assertEqual((passive["legal"], passive["violating"]), (0, -1))

    def test_unless_and_is_not_flip(self):
        unless = _proposal("Raises ValueError unless n is positive.")
        negated = _proposal("Raises ValueError if n is not positive.")
        self.assertEqual((unless["legal"], unless["violating"]), (1, 0))
        self.assertEqual((negated["legal"], negated["violating"]), (1, 0))

    def test_return_contrast_and_markup(self):
        found = _proposal("Returns ``True`` if ``n`` is zero and ``False`` otherwise.")
        self.assertTrue(found["ok"], found)
        self.assertEqual(found["pattern"], "return_if")
        self.assertEqual(found["legal"], 0)
        self.assertEqual(found["violating"], 1)
        self.assertEqual(found["human"], {"op": "return_equals", "value": True})
        else_form = _proposal("The result is true if n is even else false.")
        self.assertEqual(else_form["legal"], 0)
        self.assertEqual(else_form["violating"], 1)
        self.assertEqual(else_form["human"]["op"], "return_equals")

    def test_return_and_raise_uses_the_return_predicate(self):
        found = _proposal("Returns a nonnegative integer and raises ValueError if n is negative.")
        self.assertTrue(found["ok"], found)
        self.assertEqual(found["pattern"], "return_and_raise")
        self.assertEqual((found["legal"], found["violating"]), (0, -1))
        self.assertEqual(found["human"], {"op": "return_holds", "translation": ">=0"})

    def test_undetermined_and_extra_arguments_and_same_branch(self):
        self.assertEqual(_proposal("The result is positive.")["reason"], "inputs_not_determined_by_sentence")
        self.assertEqual(_proposal("Returns True if ready.")["reason"], "inputs_not_determined_by_sentence")
        extra = _proposal("Raises ValueError if n is negative.", parameters=("n", "m"), required=("n", "m"))
        self.assertEqual(extra["reason"], "needs_extra_arguments")
        same = _proposal("Returns True if n is zero and True otherwise.")
        self.assertEqual(linguistic("Returns True if n is zero and True otherwise.")[0], "ambiguous")
        self.assertEqual(same["reason"], "ambiguous_obligation")
        self.assertEqual(
            _proposal("Raises ValueError or TypeError if n is negative.")["reason"],
            "ambiguous_obligation",
        )

    def test_generic_parameter_rebinds_only_when_unique(self):
        rebound = _proposal("Raises ValueError if the value is negative.", parameters=("count",), required=("count",))
        self.assertTrue(rebound["ok"])
        self.assertEqual(rebound["param"], "count")
        unnamed = _proposal(
            "Raises ValueError if the value is negative.",
            parameters=("left", "right"),
            required=("left", "right"),
        )
        self.assertEqual(unnamed["reason"], "inputs_not_determined_by_sentence")

    def test_caps_duplicate_and_round_robin(self):
        state = SelectionState()
        first = judge(_candidate("Raises ValueError if n is negative.", name="alpha"), state)
        second = judge(_candidate("Raise ValueError if n is negative.", name="alpha"), state)
        third = judge(_candidate("Raises TypeError if n is zero.", name="alpha"), state)
        fourth = judge(_candidate("Raises RuntimeError if n is positive.", name="alpha"), state)
        self.assertEqual(first["decision"], "include")
        self.assertEqual(second["reason"], "duplicate_obligation")
        self.assertEqual(third["decision"], "include")
        self.assertEqual(fourth["reason"], "function_cap")
        queues = {"click": [], "requests": []}
        for index in range(5):
            queues["click"].append(_candidate(f"Raises OSError if n is greater than {index}.", name=f"c{index}"))
            queues["requests"].append(_candidate(
                f"Returns {index + 1} if n is greater than {index} else 0.",
                name=f"r{index}",
                library="requests",
            ))
        screened = examine(queues)
        included = [row for row in screened["records"] if row["decision"] == "include"]
        self.assertEqual(sum(1 for row in included if row["library"] == "click"), 4)
        self.assertEqual(sum(1 for row in included if row["library"] == "requests"), 4)
        self.assertLessEqual(len(screened["records"]), EXAMINE_CAP)
        self.assertLessEqual(len(included), INCLUDE_CAP)
        self.assertEqual(screened["stopped_because"], "pool_exhausted")
        self.assertTrue(any(row["reason"] == "library_cap" for row in screened["records"]))
        # Round-robin: the first two examined rows are different libraries.
        self.assertNotEqual(screened["records"][0]["library"], screened["records"][1]["library"])


class CollectionTests(unittest.TestCase):
    def test_module_functions_and_explicit_init_only(self):
        package = Path(tempfile.mkdtemp()) / "click"
        package.mkdir()
        (package / "__init__.py").write_text("", encoding="utf-8")
        (package / "api.py").write_text(textwrap.dedent('''\
            def alpha(n):
                """Returns True if n is zero and False otherwise."""

            def _hidden(n):
                """Raises ValueError if n is negative."""

            async def later(n):
                """Raises ValueError if n is negative."""

            class Box:
                """Ignored when init has its own text."""
                def __init__(self, n):
                    """Raises ValueError if n is negative."""
                def push(self, n):
                    """Raises ValueError if n is negative."""

            @property
            def nope(n):
                """Raises ValueError if n is negative."""
        '''), encoding="utf-8")
        library = {"pypi": "click", "roots": ("click",), "import_name": "click"}
        collected = collect_tree([package], library, "0")
        names = [item["qualname"] for item in collected["candidates"]]
        self.assertIn("click.api.alpha", names)
        self.assertIn("click.api.Box", names)
        self.assertNotIn("click.api._hidden", names)
        self.assertNotIn("click.api.push", names)
        self.assertNotIn("click.api.later", names)
        self.assertGreaterEqual(collected["skipped"].get("methods", 0), 1)
        alpha = next(item for item in collected["candidates"] if item["qualname"].endswith("alpha"))
        decision = judge(alpha, SelectionState(), collected["texts"])
        self.assertEqual(decision["decision"], "include")
        self.assertEqual(decision["pattern"], "return_if")
        tree = ast.parse((package / "api.py").read_text(encoding="utf-8"))
        self.assertTrue(any(isinstance(node, ast.FunctionDef) for node in tree.body))


class ScoreTests(unittest.TestCase):
    def test_pair_labels(self):
        self.assertEqual(pair_label("clear", "alarm"), "full_success")
        self.assertEqual(pair_label("alarm", "clear"), "inverted")
        self.assertEqual(pair_label("clear", "clear"), "hold_only")
        self.assertEqual(pair_label("alarm", "no_return"), "fail_only")
        self.assertEqual(pair_label("cannot_apply", "alarm"), "error")

    def test_sentence_match_rejects_a_neighbor(self):
        included = "Returns True if n is zero and False otherwise."
        self.assertTrue(sentence_matches(included, included))
        self.assertFalse(sentence_matches(included, "Returns 0."))

    def test_conditional_sentence_and_human_ceiling(self):
        quote = "Returns True if n is zero and False otherwise."
        legal = {"ok": True, "jsonable": True, "value": True}
        violating = {"ok": True, "jsonable": True, "value": False}
        grounded = score_grounded(quote, quote, legal, violating)
        self.assertEqual(grounded["label"], "no_check")
        self.assertFalse(grounded["emitted"])
        human = score_human({"op": "return_equals", "value": True}, legal, violating)
        self.assertEqual(human["label"], "full_success")
        raised = {"ok": False, "exc_type": "ValueError", "message": "n"}
        quiet = {"ok": True, "jsonable": True, "value": 0}
        ceiling = score_human({"op": "raises", "type": "ValueError"}, quiet, raised)
        self.assertEqual(ceiling["label"], "inverted")

    def test_bind_and_jdoctor_on_a_returns_section(self):
        quote = "The result is true if n is zero and false otherwise."
        document = "Returns:\n    The result is true if n is zero and false otherwise.\n"
        legal = {"ok": True, "jsonable": True, "value": True}
        violating = {"ok": True, "jsonable": True, "value": False}
        bound = score_translated("bind", document, quote, legal, violating)
        tagged = score_translated("jdoctor_pattern", document, quote, legal, violating)
        prose = score_translated("jdoctor_pattern", quote, quote, legal, violating)
        self.assertEqual(bound["label"], "full_success")
        self.assertEqual(tagged["label"], "full_success")
        self.assertEqual(prose["label"], "no_check")
        self.assertFalse(score_grounded(document, quote, legal, violating)["emitted"])

    def test_driver_reads_only_the_value(self):
        driver = build_driver("click.types", ["BOOL"], "n", "keyword")
        self.assertIn("def call(", driver)
        self.assertIn("click.types", driver)
        self.assertNotIn("assert", driver)
        self.assertIn("inputs['value']", driver)

    def test_decision_order(self):
        def counts(jdoctor=0, bind=0, sentence=0, human=0, jdoc_e=0, bind_e=0, sent_e=0, human_e=0):
            def block(full, executable):
                return {"full_success": full, "executable": executable}
            return {
                "jdoctor_pattern": block(jdoctor, jdoc_e),
                "bind": block(bind, bind_e),
                "sentence_grounded": block(sentence, sent_e),
                "human_from_sentence": block(human, human_e),
            }
        short = decide(7, 3, counts())
        self.assertEqual(short["decision"], "insufficient_denominator")
        self.assertIsNone(short["ranking"])
        narrow = decide(8, 2, counts())
        self.assertEqual(narrow["decision"], "insufficient_denominator")
        loss = decide(8, 3, counts(human=4, human_e=4))
        self.assertEqual(loss["decision"], "extraction_loss")
        tied = decide(8, 3, counts())
        self.assertEqual(tied["decision"], "no_new_method")
        reported = decide(8, 3, counts(bind=3, bind_e=3, human=5, human_e=5))
        self.assertEqual(reported["decision"], "counts_reported")
        self.assertIn("not_drift", reported["reason"])
        self.assertEqual(MIN_INCLUDED, 8)
        self.assertEqual(MIN_LIBRARIES, 3)
        self.assertEqual(EXAMINE_CAP, 40)
        self.assertEqual(INCLUDE_CAP, 12)

    def test_pool_and_protocol_agree(self):
        text = (HERE / "protocol.md").read_text(encoding="utf-8")
        for spec in POOL:
            self.assertIn(spec["pypi"], text)
        for banned in ("pandas", "Pillow", "SciPy"):
            self.assertIn(banned, text)
        for tool in NOT_RUN:
            self.assertIn(tool["name"], text)
        self.assertEqual(len(POOL), 19)
        self.assertEqual([spec["pypi"] for spec in POOL], [
            "click", "requests", "httpx", "pydantic", "pytest", "Jinja2", "flask",
            "werkzeug", "marshmallow", "jsonschema", "python-dateutil", "arrow",
            "attrs", "rich", "hypothesis", "lxml", "beautifulsoup4", "PyYAML", "tomli",
        ])
        for name in EXTRACTORS:
            self.assertIn(name, text)
        self.assertNotIn("documented_predicate_binding", "".join(spec["pypi"] for spec in POOL))


if __name__ == "__main__":
    unittest.main()
