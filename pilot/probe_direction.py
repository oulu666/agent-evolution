"""Direction-semantics and action-token probe for the small Sokoban student.

Solve conditions
  base     the prompt used in astra_qwen.py and learn.py
  box      explicit "reply with the direction the BOX moves, not the player"
  example  box wording plus a worked example
  words    reply with the words up/down/left/right instead of U/D/L/R
  permute  reply with symbols A/B/C/D mapped to up/down/left/right
  think    state the box direction in a sentence, then give the label

Two-question probe, per board
  box      which direction should the BOX move?
  player   which side of the box must the PLAYER stand on?

Logprob probe
  ask for the first action with logprobs and report the probability mass on
  the optimal and reverse directions.

Board sets: T0/T1 are the 24-board forms from learn.py; pilot is the original
12 boards in astra_qwen_20261106/boards.json.

Serve Qwen on localhost:18946 and set ASTRA_API_KEY, as in astra_qwen.py.
A student-only run over pilot makes about 600 local calls and 12 logprob calls.
"""
from collections import Counter
import argparse
import csv
import json
import math
from pathlib import Path
import re
from statistics import mean

import astra_qwen as base
from diagnose import make_distance
import learn
from push import choices
from run import board

HERE = Path(__file__).resolve().parent
OUT = HERE / "probe_20261108"
OPPOSITE = {"U": "D", "D": "U", "L": "R", "R": "L"}
CONDITIONS = ("base", "box", "example", "words", "permute", "think")
MAX_ACTIONS = 8
SYMBOL_OF = {"U": "A", "D": "B", "L": "C", "R": "D"}
DIRECTION_OF_SYMBOL = {symbol: direction for direction, symbol in SYMBOL_OF.items()}
WORD_OF = {"U": "up", "D": "down", "L": "left", "R": "right"}
DIRECTION_OF_WORD = {word: direction for direction, word in WORD_OF.items()}
BOX_RULE = ("\nIMPORTANT: U/D/L/R describe the direction the BOX moves. They do NOT describe "
            "the direction the player walks or the side where the player stands. Example: to "
            "push the box left, reply L even if the player must first walk to the right side "
            "of the box.")
EXTRAS = {
    "base": "",
    "box": BOX_RULE,
    "example": (BOX_RULE + "\nWorked example: the box is at (2, 2) and the goal is at "
                "(0, 2). The box must move LEFT, so the correct reply is L. The player will "
                "automatically walk to the right side of the box. Do not reply R."),
    "words": ("\nThe action labels in this task are the words up, down, left and right. "
              "Reply with one word."),
    "permute": ("\nThe action labels in this task are symbols: A means up, B means down, "
                "C means left, D means right. Reply with one symbol."),
    "think": (BOX_RULE + "\nBefore choosing, state in one short sentence which direction the "
              "BOX should move. Then on a new line reply with exactly one of U, D, L, R."),
}


def header(case, condition):
    floors = set(map(tuple, case["floors"]))
    start = tuple(case["player"]), tuple(case["box"])
    goal = tuple(case["goal"])
    return (base.RULES + EXTRAS[condition] + "\nInitial board:\n" +
            board(floors, start, goal) +
            f"\nInitial history: attempted to walk {case['blocked']} twice, both blocked.")


def start_sets(case):
    floors = set(map(tuple, case["floors"]))
    start = tuple(case["player"]), tuple(case["box"])
    dist = make_distance(floors, tuple(case["goal"]))
    d0 = dist(start)
    optimal = {direction for direction, nxt in choices(floors, start).items()
               if dist(nxt) == d0 - 1}
    return optimal, {OPPOSITE[direction] for direction in optimal}


def format_options(options, condition):
    if condition == "words":
        return [WORD_OF[direction] for direction in options]
    if condition == "permute":
        return [SYMBOL_OF[direction] for direction in options]
    return list(options)


def instruction(condition):
    if condition == "words":
        return "\nReply with one word: up, down, left, or right."
    if condition == "permute":
        return "\nReply with one symbol: A, B, C, or D."
    if condition == "think":
        return ("\nFirst state which direction the BOX should move, then reply with one "
                "label on a new line.")
    if condition in ("box", "example"):
        return ("\nReply with just its label. Remember: the label is the direction the BOX "
                "moves, not the direction the player walks or the side where the player "
                "stands.")
    return "\nReply with just its label."


def parse_action(text, condition):
    raw = text.strip()
    upper = raw.upper()
    if upper == "RESET" or upper.startswith("RESET"):
        return "RESET", "RESET"
    if condition == "words":
        match = re.search(r"\b(up|down|left|right)\b", raw, re.IGNORECASE)
        if match:
            word = match.group(1).lower()
            return DIRECTION_OF_WORD[word], word
        return None, raw
    if condition == "permute":
        match = re.search(r"\b([ABCD])\b", upper)
        if match:
            symbol = match.group(1)
            return DIRECTION_OF_SYMBOL[symbol], symbol
        return None, raw
    if condition == "think":
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        if lines:
            match = re.fullmatch(r"([UDLR])", lines[-1].upper())
            if match:
                return match.group(1), match.group(1)
        matches = re.findall(r"\b([UDLR])\b", upper)
        if matches:
            return matches[-1], matches[-1]
        match = re.search(r"\b(up|down|left|right)\b", raw, re.IGNORECASE)
        if match:
            word = match.group(1).lower()
            return DIRECTION_OF_WORD[word], word
        return None, raw
    match = re.fullmatch(r"(RESET|[UDLR])", upper)
    if match:
        return match.group(1), match.group(1)
    return None, raw


def solve(case, condition, actor="student"):
    floors = set(map(tuple, case["floors"]))
    start = tuple(case["player"]), tuple(case["box"])
    goal = tuple(case["goal"])
    state = start
    head = header(case, condition)
    calls = []
    moves = []
    displays = []
    while len(moves) < MAX_ACTIONS and state[1] != goal:
        options = choices(floors, state)
        labels = format_options(options, condition)
        prompt = (head + "\nActions taken: " + " ".join(displays) +
                  "\nCurrent board:\n" + board(floors, state, goal) +
                  "\nAvailable actions: " + " ".join([*labels, "RESET"]) +
                  "\nChoose one available action." + instruction(condition))
        call = (learn.ask_student(prompt, 64 if condition == "think" else 16)
                if actor == "student" else base.call(base.TEACHER, prompt))
        calls.append(call)
        direction, display = parse_action(call["output"], condition)
        if direction == "RESET":
            state = start
            moves.append("RESET")
            displays.append("RESET")
        elif direction in options:
            state = options[direction]
            moves.append(direction)
            displays.append(display)
        else:
            invalid = "INVALID(" + call["output"].strip() + ")"
            moves.append(invalid)
            displays.append(invalid)
    optimal, reverse = start_sets(case)
    first = moves[0] if moves else None
    first_class = ("optimal" if first in optimal else
                   "reverse" if first in reverse else "other")
    row = dict(id=case["id"], condition=condition, actor=actor,
               solved=state[1] == goal, moves=moves, actions=displays,
               first=first, first_class=first_class,
               tokens=sum(call["total_tokens"] for call in calls), calls=calls)
    learn.verify_row(case, dict(row, actions=moves))
    return row


def twoq(case, actor="student"):
    head = header(case, "base")
    box_prompt = (head + "\nQuestion: which direction should the BOX move next so that it gets "
                  "closer to the goal? Reply with exactly one of U, D, L, R, meaning the "
                  "direction the box moves.")
    player_prompt = (head + "\nQuestion: to push the box toward the goal, the player must stand "
                     "on one side of the box. Which side of the box must the player stand on? "
                     "Reply with exactly one of U, D, L, R, meaning the side of the box the "
                     "player occupies. Example: to push the box left, the player stands on the "
                     "box's right side, so the answer is R.")
    box_call = (learn.ask_student(box_prompt, 12) if actor == "student"
                else base.call(base.TEACHER, box_prompt))
    player_call = (learn.ask_student(player_prompt, 12) if actor == "student"
                   else base.call(base.TEACHER, player_prompt))
    optimal, reverse = start_sets(case)
    box_answer = parse_label(box_call["output"])
    player_answer = parse_label(player_call["output"])
    return dict(id=case["id"], actor=actor, box_call=box_call, player_call=player_call,
                q_box=box_answer, q_player=player_answer,
                box_correct=box_answer in optimal,
                player_correct=player_answer in reverse,
                tokens=box_call["total_tokens"] + player_call["total_tokens"])


def parse_label(text):
    match = re.search(r"[UDLR]", text.upper())
    return match.group(0) if match else None


def direction_of_token(token):
    text = re.sub(r"[^A-Z]", "", token.upper())
    if text in ("U", "D", "L", "R"):
        return text
    return {"UP": "U", "DOWN": "D", "LEFT": "L", "RIGHT": "R"}.get(text)


def logprob_probe(case):
    floors = set(map(tuple, case["floors"]))
    start = tuple(case["player"]), tuple(case["box"])
    goal = tuple(case["goal"])
    options = choices(floors, start)
    prompt = (header(case, "base") + "\nActions taken: " +
              "\nCurrent board:\n" + board(floors, start, goal) +
              "\nAvailable actions: " + " ".join([*options, "RESET"]) +
              "\nChoose one available action. Reply with just its label.")
    payload = dict(model=base.STUDENT, messages=[{"role": "user", "content": prompt}],
                   temperature=0, seed=base.SEED, max_tokens=2,
                   logprobs=True, top_logprobs=20)
    try:
        data = base.post(learn.STUDENT_URL, payload)
    except Exception as exc:
        return dict(id=case["id"], error=str(exc), done=True)
    choice = data["choices"][0]
    content = (choice.get("logprobs") or {}).get("content") or []
    probabilities = {}
    position = None
    top = []
    for index, item in enumerate(content):
        entries = item.get("top_logprobs") or []
        mapped = {}
        for entry in entries:
            direction = direction_of_token(entry.get("token", ""))
            if direction:
                mapped[direction] = mapped.get(direction, 0.0) + math.exp(entry["logprob"])
        if mapped:
            probabilities, position = mapped, index
            top = [dict(token=entry.get("token"), logprob=entry.get("logprob"),
                        direction=direction_of_token(entry.get("token", "")))
                   for entry in entries]
            break
    optimal, reverse = start_sets(case)
    total = sum(probabilities.values())
    row = dict(id=case["id"], chosen=choice.get("message", {}).get("content", "").strip(),
               probabilities=probabilities, mass=round(total, 4),
               prob_optimal=round(sum(probabilities.get(d, 0.0) for d in optimal), 4),
               prob_reverse=round(sum(probabilities.get(d, 0.0) for d in reverse), 4),
               optimal=sorted(optimal), reverse=sorted(reverse),
               argmax=max(probabilities, key=probabilities.get) if probabilities else None,
               position=position, top=top, error=None, done=True)
    if not probabilities:
        row["error"] = "no direction token in top_logprobs"
    return row


def read_row(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def solve_job(case, condition, actor, root):
    directory = root / condition if actor == "student" else root / "teacher" / condition
    path = directory / f"{case['id']}.json"
    row = read_row(path)
    if row and row.get("done"):
        return row
    row = solve(case, condition, actor)
    row["done"] = True
    learn.save(path, row)
    print("solve", actor, condition, case["id"], row["first_class"],
          row["solved"], row["tokens"], flush=True)
    return row


def twoq_job(case, actor, root):
    directory = root / "twoq" if actor == "student" else root / "teacher" / "twoq"
    path = directory / f"{case['id']}.json"
    row = read_row(path)
    if row and row.get("done"):
        return row
    row = twoq(case, actor)
    row["done"] = True
    learn.save(path, row)
    print("twoq", actor, case["id"], row["q_box"], row["q_player"],
          row["box_correct"], row["player_correct"], flush=True)
    return row


def logprob_job(case, root):
    path = root / "logprobs" / f"{case['id']}.json"
    row = read_row(path)
    if row and row.get("done"):
        return row
    row = logprob_probe(case)
    learn.save(path, row)
    print("logprob", case["id"], row.get("argmax"), row.get("prob_optimal"),
          row.get("prob_reverse"), row.get("error"), flush=True)
    return row


def load_rows(directory):
    return [json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(directory.glob("*.json"))]


def condition_summary(rows):
    if not rows:
        return dict(n=0)
    classes = Counter(row["first_class"] for row in rows)
    return dict(n=len(rows), solved=sum(row["solved"] for row in rows),
                first_optimal=classes["optimal"], first_reverse=classes["reverse"],
                first_other=classes["other"],
                mean_tokens=round(sum(row["tokens"] for row in rows) / len(rows)))


def twoq_summary(rows, base_rows):
    if not rows:
        return dict(n=0)
    result = dict(n=len(rows),
                  box_correct=sum(row["box_correct"] for row in rows),
                  player_correct=sum(row["player_correct"] for row in rows))
    if not all(row["id"] in base_rows for row in rows):
        return result
    action_matches_box = sum(base_rows[row["id"]]["first"] == row["q_box"] for row in rows)
    action_matches_player = sum(base_rows[row["id"]]["first"] == row["q_player"] for row in rows)
    box_ok_action_player = sum(row["box_correct"] and
                               base_rows[row["id"]]["first"] == row["q_player"] for row in rows)
    result.update(
        action_matches_box=action_matches_box,
        action_matches_player=action_matches_player,
        box_correct_and_action_player=box_ok_action_player,
        per_board=[dict(id=row["id"], q_box=row["q_box"], q_player=row["q_player"],
                        box_correct=row["box_correct"],
                        player_correct=row["player_correct"],
                        action=base_rows[row["id"]]["first"],
                        action_class=base_rows[row["id"]]["first_class"]) for row in rows])
    return result


def logprob_summary(rows):
    if not rows:
        return dict(n=0)
    valid = [row for row in rows if not row.get("error")]
    if not valid:
        return dict(n=len(rows), valid=0,
                    errors=sorted({row.get("error", "")[:80] for row in rows}))
    return dict(
        n=len(rows), valid=len(valid),
        mean_prob_optimal=round(mean(row["prob_optimal"] for row in valid), 3),
        mean_prob_reverse=round(mean(row["prob_reverse"] for row in valid), 3),
        argmax_optimal=sum(row["argmax"] in row["optimal"] for row in valid),
        argmax_reverse=sum(row["argmax"] in row["reverse"] for row in valid),
        per_board=[dict(id=row["id"], chosen=row["chosen"], argmax=row["argmax"],
                        prob_optimal=row["prob_optimal"], prob_reverse=row["prob_reverse"],
                        position=row["position"]) for row in valid])


def write_csv(root, conditions, wanted):
    fields = ["condition", "actor", "id", "solved", "first", "first_class", "tokens",
              "moves", "actions"]
    with (root / "traces.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for condition in conditions:
            for row in load_rows(root / condition):
                if row["id"] in wanted:
                    writer.writerow(dict(condition=condition, actor=row["actor"], id=row["id"],
                                         solved=row["solved"], first=row["first"],
                                         first_class=row["first_class"], tokens=row["tokens"],
                                         moves=" ".join(row["moves"]),
                                         actions=" ".join(row["actions"])))
    with (root / "twoq.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["id", "q_box", "q_player",
                                                    "box_correct", "player_correct"])
        writer.writeheader()
        for row in load_rows(root / "twoq"):
            if row["id"] in wanted:
                writer.writerow(dict(id=row["id"], q_box=row["q_box"], q_player=row["q_player"],
                                     box_correct=row["box_correct"],
                                     player_correct=row["player_correct"]))
    with (root / "logprobs.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["id", "chosen", "argmax", "prob_optimal",
                                                    "prob_reverse", "mass", "error"])
        writer.writeheader()
        for row in load_rows(root / "logprobs"):
            if row["id"] in wanted:
                writer.writerow(dict(id=row["id"], chosen=row.get("chosen"),
                                     argmax=row.get("argmax"),
                                     prob_optimal=row.get("prob_optimal"),
                                     prob_reverse=row.get("prob_reverse"),
                                     mass=row.get("mass"), error=row.get("error")))


def summarize(root, cases, conditions):
    wanted = {case["id"] for case in cases}

    def rows_for(directory):
        return [row for row in load_rows(directory) if row["id"] in wanted]

    summary = {"boards": len(cases), "conditions": {}, "twoq": {}, "logprobs": {},
               "teacher": {}}
    for condition in conditions:
        summary["conditions"][condition] = condition_summary(rows_for(root / condition))
    base_condition = "base" if "base" in conditions else (conditions[0] if conditions else None)
    twoq_rows = rows_for(root / "twoq") if (root / "twoq").exists() else []
    if twoq_rows and base_condition:
        summary["twoq"] = twoq_summary(
            twoq_rows, {row["id"]: row for row in rows_for(root / base_condition)})
    logprob_rows = rows_for(root / "logprobs") if (root / "logprobs").exists() else []
    if logprob_rows:
        summary["logprobs"] = logprob_summary(logprob_rows)
    teacher = root / "teacher"
    if (teacher / "box").exists():
        summary["teacher"]["box"] = condition_summary(rows_for(teacher / "box"))
    if (teacher / "twoq").exists():
        teacher_rows = rows_for(teacher / "twoq")
        summary["teacher"]["twoq"] = dict(
            n=len(teacher_rows),
            box_correct=sum(row["box_correct"] for row in teacher_rows),
            player_correct=sum(row["player_correct"] for row in teacher_rows))
    learn.save(root / "summary.json", summary)
    write_csv(root, conditions, wanted)
    print(json.dumps(summary, indent=2))
    return summary


def load_cases(name):
    if name == "pilot":
        raw = json.loads((HERE / "astra_qwen_20261106" / "boards.json").read_text(encoding="utf-8"))
        return [dict(case, id=f"P-{case['id']:02d}") for case in raw]
    return learn.load_sets()[name]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--boards", default="T0", choices=("T0", "T1", "pilot"))
    parser.add_argument("--conditions", nargs="+", default=list(CONDITIONS),
                        choices=CONDITIONS)
    parser.add_argument("--stage", default="all",
                        choices=("all", "solve", "twoq", "logprob", "summary"))
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--teacher", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    cases = load_cases(args.boards)
    if args.limit:
        cases = cases[:args.limit]
    root = OUT / args.boards
    root.mkdir(parents=True, exist_ok=True)
    if args.stage in ("all", "solve"):
        for condition in args.conditions:
            learn.parallel(lambda case: solve_job(case, condition, "student", root),
                           cases, args.workers)
        if args.teacher:
            learn.parallel(lambda case: solve_job(case, "box", "teacher", root),
                           cases, args.workers)
    if args.stage in ("all", "twoq"):
        learn.parallel(lambda case: twoq_job(case, "student", root), cases, args.workers)
        if args.teacher:
            learn.parallel(lambda case: twoq_job(case, "teacher", root), cases, args.workers)
    if args.stage in ("all", "logprob"):
        learn.parallel(lambda case: logprob_job(case, root), cases, args.workers)
    if args.stage in ("all", "summary"):
        summarize(root, cases, args.conditions)


if __name__ == "__main__":
    main()
