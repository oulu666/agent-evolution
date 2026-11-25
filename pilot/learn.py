"""Independent-test learning experiment for the Sokoban teacher/student pilot.

Stages
  sets      generate and validate the teaching set and two parallel test forms
  baseline  student solves T0 and T1 alone, predicting success per board first
  teach     full teacher guidance on the teaching set, plus a student-alone practice run
  lesson    student-taught, student-practice, teacher-written and unrelated lessons
  post      student solves T1 alone with one lesson artifact per arm
  reflect   student revises its lesson after seeing the test outcomes
  summary   paired gains, token cost, behavior markers and calibration

Serve Qwen on localhost:18946 (see astra_qwen.py) and set ASTRA_API_KEY.
A full run makes about 1.6k local calls and 100 teacher calls; every stage resumes.
"""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import argparse
import csv
import json
import re
from statistics import mean

import astra_qwen as base
from push import choices
from run import DIR, board, make_cases

TRAIN_SEED = 20261109
FORMS = {"T0": (20261107, 20261108), "T1": (20261110, 20261111)}
ARMS = ("taught", "practice", "teacher_lesson", "irrelevant")
OUT = base.HERE / "learn_20261107"
MAX_ACTIONS = 8
STUDENT_URL = "http://127.0.0.1:18946/v1/chat/completions"


def ask_student(prompt, max_tokens=16):
    data = base.post(STUDENT_URL, dict(
        model=base.STUDENT, messages=[{"role": "user", "content": prompt}],
        temperature=0, seed=base.SEED, max_tokens=max_tokens))
    answer = data["choices"][0]["message"]["content"].strip()
    usage = data["usage"]
    if data["model"] != base.STUDENT or not answer:
        raise ValueError(f"Unexpected student response from {data.get('model')!r}")
    return dict(model=base.STUDENT, prompt=prompt, output=answer,
                input_tokens=usage["prompt_tokens"],
                output_tokens=usage["completion_tokens"],
                reasoning_tokens=0, total_tokens=usage["total_tokens"])


def read_row(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def parallel(fn, items, workers):
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(fn, items))


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    base.save(path, data)


def signature(case):
    return (tuple(sorted(map(tuple, case["floors"]))), tuple(case["player"]),
            tuple(case["box"]), tuple(case["goal"]))


def load_sets():
    train = [dict(c, id=f"S-{c['id']:02d}") for c in make_cases(TRAIN_SEED)]
    forms = {}
    for form, seeds in FORMS.items():
        forms[form] = [dict(c, id=f"{form}-{seed}-{c['id']:02d}")
                       for seed in seeds for c in make_cases(seed)]
    sets = {"train": train, **forms}
    check_sets(sets)
    return sets


def check_sets(sets):
    seen = {}
    for name, cases in sets.items():
        for case in cases:
            sig = signature(case)
            if sig in seen:
                raise SystemExit(f"Duplicate board {case['id']} in {name}; also {seen[sig]}")
            seen[sig] = case["id"]
    assert len(sets["train"]) == 12
    strata = None
    for form in FORMS:
        assert len(sets[form]) == 24
        counts = Counter("easy" if c["optimal_steps"] <= 7 else "hard"
                         for c in sets[form])
        strata = strata or counts
        if counts != strata:
            raise SystemExit(f"Unbalanced test forms: {form} has {dict(counts)}")


def set_info(name, cases):
    return dict(n=len(cases),
                seeds=TRAIN_SEED if name == "train" else list(FORMS[name]),
                strata=dict(Counter("easy" if c["optimal_steps"] <= 7 else "hard"
                                    for c in cases)),
                steps=[c["optimal_steps"] for c in cases])


def write_sets(sets):
    OUT.mkdir(exist_ok=True)
    path = OUT / "sets.json"
    if path.exists():
        saved = json.loads(path.read_text(encoding="utf-8"))
        old = {name: [signature(case) for case in cases] for name, cases in saved.items()}
        new = {name: [signature(case) for case in cases] for name, cases in sets.items()}
        if old != new:
            raise SystemExit("sets.json does not match the current seeds; use a new OUT "
                             "directory or restore the original seeds.")
    save(path, sets)
    with (OUT / "sets.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["set", "case", "optimal_steps", "floors"])
        for name, cases in sets.items():
            for case in cases:
                writer.writerow([name, case["id"], case["optimal_steps"], len(case["floors"])])


def header(case):
    floors = set(map(tuple, case["floors"]))
    start = tuple(case["player"]), tuple(case["box"])
    goal = tuple(case["goal"])
    return (base.RULES + "\nInitial board:\n" + board(floors, start, goal) +
            f"\nInitial history: attempted to walk {case['blocked']} twice, both blocked.")


def is_deadlock(floors, state, goal):
    box = state[1]
    if box == goal:
        return False
    walls = [d for d, (dx, dy) in DIR.items()
             if (box[0] + dx, box[1] + dy) not in floors]
    if not walls:
        return False
    for direction in walls:
        if direction in "UD" and goal[1] == box[1]:
            return False
        if direction in "LR" and goal[0] == box[0]:
            return False
    return True


def verify_row(case, row):
    floors = set(map(tuple, case["floors"]))
    start = tuple(case["player"]), tuple(case["box"])
    goal = tuple(case["goal"])
    state = start
    for action in row["actions"]:
        if action == "RESET":
            state = start
        elif not action.startswith("INVALID("):
            state = choices(floors, state)[action]
    assert row["solved"] == (state[1] == goal), row["id"]
    assert row["tokens"] == sum(call["total_tokens"] for call in row["calls"]), row["id"]


def parse_prediction(text):
    numbers = re.findall(r"\b(\d{1,3})\b", text)
    if not numbers:
        return None
    value = int(numbers[-1])
    return value if 0 <= value <= 100 else None


def solve(case, lesson="", predict=True):
    floors = set(map(tuple, case["floors"]))
    start = tuple(case["player"]), tuple(case["box"])
    goal = tuple(case["goal"])
    state = start
    head = header(case)
    lesson_text = "\nLesson:\n" + lesson if lesson else ""
    calls = []
    prediction = None
    if predict:
        prompt = (head + lesson_text +
                  "\nBefore acting, predict the probability (0-100) that you will solve this "
                  "board within 8 pushes. Reply with one integer and nothing else.")
        call = ask_student(prompt, max_tokens=12)
        calls.append(call)
        prediction = parse_prediction(call["output"])
    actions = []
    deadlock = False
    while len(actions) < MAX_ACTIONS and state[1] != goal:
        options = choices(floors, state)
        prompt = (head + lesson_text + "\nActions taken: " + " ".join(actions) +
                  "\nCurrent board:\n" + board(floors, state, goal) +
                  "\nAvailable actions: " + " ".join([*options, "RESET"]) +
                  "\nChoose one available action. Reply with just its label.")
        call = ask_student(prompt, max_tokens=16)
        calls.append(call)
        match = re.fullmatch(r"(RESET|[UDLR])", call["output"].upper())
        label = match[1] if match else "INVALID"
        if label == "RESET":
            state = start
        elif label in options:
            state = options[label]
        else:
            label = "INVALID(" + call["output"] + ")"
        actions.append(label)
        if state[1] != goal and is_deadlock(floors, state, goal):
            deadlock = True
    solve_calls = calls[1:] if predict else calls
    row = dict(id=case["id"], solved=state[1] == goal, actions=actions, calls=calls,
               prediction=prediction, deadlock=deadlock,
               tokens=sum(call["total_tokens"] for call in calls),
               solve_tokens=sum(call["total_tokens"] for call in solve_calls))
    verify_row(case, row)
    return row


def baseline_job(form, case):
    path = OUT / "baseline" / form / f"{case['id']}.json"
    row = read_row(path)
    if row and row.get("done"):
        return row
    row = solve(case, "")
    row.update(done=True, form=form)
    save(path, row)
    print("baseline", form, case["id"], row["solved"], row["tokens"], flush=True)
    return row


def teach_guided(case):
    path = OUT / "teach" / "guided" / f"{case['id']}.json"
    row = read_row(path)
    if row and row.get("done"):
        return row
    row = row or dict(id=case["id"], calls=[], actions=[])
    floors = set(map(tuple, case["floors"]))
    start = tuple(case["player"]), tuple(case["box"])
    goal = tuple(case["goal"])
    state = start
    for action in row["actions"]:
        state = start if action == "RESET" else choices(floors, state).get(action, state)
    head = header(case)
    while len(row["actions"]) < MAX_ACTIONS and state[1] != goal:
        options = choices(floors, state)
        observation = ("\nCurrent board:\n" + board(floors, state, goal) +
                       "\nAvailable actions: " + " ".join([*options, "RESET"]))
        if len(row["calls"]) == 2 * len(row["actions"]):
            previous = ""
            if row["calls"]:
                previous = "\nYour previous instruction:\n" + row["calls"][-2]["output"]
            prompt = (head + "\nStudent actions taken: " + " ".join(row["actions"]) +
                      observation + previous +
                      "\nYou supervise a smaller model that executes one action at a time. "
                      "Solve the whole remaining task and give a complete ordered action plan. "
                      "Explicitly state the ONE action the student must execute now. "
                      "Check whether the previous instruction was followed and correct mistakes. "
                      "Include a brief expected state after the next action. Be concise.")
            advice = base.call(base.TEACHER, prompt)
            advice["kind"] = "full_guidance"
            row["calls"].append(advice)
            save(path, row)
        prompt = (head + "\nActions taken: " + " ".join(row["actions"]) + observation +
                  "\nTeacher instructions:\n" + row["calls"][-1]["output"] +
                  "\nExecute the teacher's requested next action. Reply with just one label "
                  "from the available actions.")
        move = ask_student(prompt, max_tokens=16)
        row["calls"].append(move)
        match = re.fullmatch(r"(RESET|[UDLR])", move["output"].upper())
        label = match[1] if match else "INVALID"
        if label == "RESET":
            state = start
        elif label in options:
            state = options[label]
        else:
            label = "INVALID(" + move["output"] + ")"
        row["actions"].append(label)
        save(path, row)
    row.update(done=True, solved=state[1] == goal,
               tokens=sum(call["total_tokens"] for call in row["calls"]))
    verify_row(case, row)
    save(path, row)
    print("teach", case["id"], row["solved"], row["tokens"], flush=True)
    return row


def teach_practice(case):
    path = OUT / "teach" / "practice" / f"{case['id']}.json"
    row = read_row(path)
    if row and row.get("done"):
        return row
    row = solve(case, "", predict=False)
    row["done"] = True
    save(path, row)
    print("practice", case["id"], row["solved"], row["tokens"], flush=True)
    return row


def load_rows(directory):
    return [json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(directory.glob("*.json"))]


def transcript(cases, rows, teacher):
    by_id = {case["id"]: case for case in cases}
    blocks = []
    for row in sorted(rows, key=lambda item: item["id"]):
        case = by_id[row["id"]]
        floors = set(map(tuple, case["floors"]))
        start = tuple(case["player"]), tuple(case["box"])
        goal = tuple(case["goal"])
        block = "Board:\n" + board(floors, start, goal)
        if teacher:
            plans = [call["output"] for call in row["calls"]
                     if call.get("kind") == "full_guidance"]
            plan = plans[-1] if plans else ""
            block += "\nTeacher plan: " + " ".join(plan.split()[:80])
        block += "\nActions: " + " ".join(row["actions"])
        blocks.append(block)
    return "\n\n".join(blocks)


def make_lesson(cases, rows, teacher, intro):
    target = ("the smaller model" if teacher else "you")
    prompt = (intro + " Below are the boards, the guidance and the actions taken.\n\n" +
              transcript(cases, rows, teacher) +
              f"\n\nWrite at most 6 short general rules (each at most 25 words) that would help "
              f"{target} solve NEW boards on its own. Rules must be general; do not include "
              "specific board layouts or exact move sequences. Number them 1-6.")
    call = base.call(base.TEACHER, prompt) if teacher else ask_student(prompt, max_tokens=256)
    return call


def write_lesson(arm, call):
    directory = OUT / "arms" / arm
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "lesson.txt").write_text(call["output"], encoding="utf-8")
    save(directory / "lesson_call.json", call)
    print("lesson", arm, len(call["output"].split()), "words", flush=True)


def lesson_exists(arm):
    return (OUT / "arms" / arm / "lesson.txt").exists()


def write_lessons(sets, arms):
    needed = [arm for arm in ("taught", "teacher_lesson")
              if arm in arms and not lesson_exists(arm)]
    if needed:
        guided = load_rows(OUT / "teach" / "guided")
        if len(guided) != len(sets["train"]) or not all(row.get("done") for row in guided):
            raise SystemExit("Guided teaching is incomplete; run --stage teach first.")
        if "taught" in needed:
            write_lesson("taught", make_lesson(
                sets["train"], guided, teacher=False,
                intro="You just solved the following Sokoban boards with a teacher's "
                      "step-by-step guidance."))
        if "teacher_lesson" in needed:
            write_lesson("teacher_lesson", make_lesson(
                sets["train"], guided, teacher=True,
                intro="You just supervised a smaller model on the following Sokoban boards, "
                      "one action at a time."))
    if "practice" in arms and not lesson_exists("practice"):
        practice = load_rows(OUT / "teach" / "practice")
        if len(practice) != len(sets["train"]) or not all(row.get("done") for row in practice):
            raise SystemExit("Practice teaching is incomplete; run --stage teach first.")
        write_lesson("practice", make_lesson(
            sets["train"], practice, teacher=False,
            intro="You just practiced the following Sokoban boards on your own."))
    if "irrelevant" in arms and not lesson_exists("irrelevant"):
        prompt = ("Write at most 6 short general rules for playing chess openings well. "
                  "Number them 1-6. Do not mention boxes, Sokoban, grids or pushing.")
        write_lesson("irrelevant", ask_student(prompt, max_tokens=256))


def post_job(arm, case):
    path = OUT / "post" / arm / "T1" / f"{case['id']}.json"
    row = read_row(path)
    if row and row.get("done"):
        return row
    lesson = (OUT / "arms" / arm / "lesson.txt").read_text(encoding="utf-8")
    row = solve(case, lesson)
    row.update(done=True, arm=arm, form="T1")
    save(path, row)
    print("post", arm, case["id"], row["solved"], row["tokens"], flush=True)
    return row


def run_reflect(arm, cases):
    path = OUT / "arms" / arm / "reflection.txt"
    if path.exists():
        print("reflection", arm, "exists", flush=True)
        return
    lesson = (OUT / "arms" / arm / "lesson.txt").read_text(encoding="utf-8")
    rows = load_rows(OUT / "post" / arm / "T1")
    if len(rows) != len(cases):
        raise SystemExit(f"Post-test for {arm} is incomplete; run --stage post first.")
    by_id = {case["id"]: case for case in cases}
    outcomes = []
    for row in rows:
        case = by_id[row["id"]]
        floors = set(map(tuple, case["floors"]))
        start = tuple(case["player"]), tuple(case["box"])
        goal = tuple(case["goal"])
        outcomes.append(board(floors, start, goal) + "\n" +
                        ("solved" if row["solved"] else "failed") + " | " +
                        " ".join(row["actions"]))
    prompt = ("You wrote this lesson:\n" + lesson +
              f"\n\nOn an independent test you solved {sum(row['solved'] for row in rows)} "
              f"of {len(rows)} boards. Per-board outcomes and actions:\n\n" +
              "\n\n".join(outcomes) +
              "\n\nRevise the lesson: keep rules the test supports, rewrite or drop the rest. "
              "Reply with at most 6 numbered rules, each at most 25 words. No board-specific "
              "layouts or exact move sequences.")
    call = ask_student(prompt, max_tokens=256)
    save(OUT / "arms" / arm / "reflection_call.json", call)
    path.write_text(call["output"], encoding="utf-8")
    print("reflection", arm, len(call["output"].split()), "words", flush=True)


def calibration(rows):
    pairs = [(row["prediction"] / 100, float(row["solved"])) for row in rows
             if row.get("prediction") is not None]
    if not pairs:
        return dict(predicted=0)
    probabilities, outcomes = zip(*pairs)
    bins = 5
    ece = 0.0
    for index in range(bins):
        low, high = index / bins, (index + 1) / bins
        chosen = [i for i, value in enumerate(probabilities)
                  if low <= value < high or (index == bins - 1 and value == 1)]
        if chosen:
            gap = abs(mean(probabilities[i] for i in chosen) -
                      mean(outcomes[i] for i in chosen))
            ece += len(chosen) / len(probabilities) * gap
    return dict(predicted=len(probabilities),
                mean_prediction=round(mean(probabilities), 3),
                accuracy=round(mean(outcomes), 3),
                brier=round(mean((p - y) ** 2 for p, y in pairs), 3),
                ece=round(ece, 3))


def row_metrics(rows):
    if not rows:
        return dict(n=0)
    wins = sum(1 for row in rows if row["solved"])
    return dict(n=len(rows), wins=wins, rate=round(wins / len(rows), 3),
                mean_tokens=round(mean(row["tokens"] for row in rows)),
                mean_solve_tokens=round(mean(row["solve_tokens"] for row in rows)),
                resets=sum(row["actions"].count("RESET") for row in rows),
                invalids=sum(sum(action.startswith("INVALID(") for action in row["actions"])
                             for row in rows),
                deadlocks=sum(1 for row in rows if row["deadlock"]),
                **calibration(rows))


def paired(baseline, post):
    before = {row["id"]: row for row in baseline}
    assert {row["id"] for row in post} == set(before)
    counts = dict(gained=0, lost=0, both_solved=0, neither=0)
    for row in post:
        old, new = before[row["id"]]["solved"], row["solved"]
        if new and not old:
            counts["gained"] += 1
        elif old and not new:
            counts["lost"] += 1
        elif new:
            counts["both_solved"] += 1
        else:
            counts["neither"] += 1
    return counts


def write_rows_csv(baseline, arms):
    fields = ["form", "arm", "case", "solved", "prediction", "deadlock", "tokens",
              "solve_tokens", "actions"]
    with (OUT / "rows.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for form, rows in baseline.items():
            for row in rows:
                writer.writerow(dict(form=form, arm="baseline", case=row["id"],
                                     solved=row["solved"], prediction=row["prediction"],
                                     deadlock=row["deadlock"], tokens=row["tokens"],
                                     solve_tokens=row["solve_tokens"],
                                     actions=" ".join(row["actions"])))
        for arm in arms:
            for row in load_rows(OUT / "post" / arm / "T1"):
                writer.writerow(dict(form="T1", arm=arm, case=row["id"],
                                     solved=row["solved"], prediction=row["prediction"],
                                     deadlock=row["deadlock"], tokens=row["tokens"],
                                     solve_tokens=row["solve_tokens"],
                                     actions=" ".join(row["actions"])))


def print_table(summary):
    print(f"{'condition':<16} {'form':<4} {'wins':>5} {'rate':>6} {'brier':>6} {'ece':>6} "
          f"{'tokens':>7}")
    for form, metrics in summary["baseline"].items():
        print(f"{'baseline':<16} {form:<4} {metrics['wins']:>5} {metrics['rate']:>6.3f} "
              f"{metrics.get('brier', 0):>6.3f} {metrics.get('ece', 0):>6.3f} "
              f"{metrics['mean_tokens']:>7}")
    for arm, metrics in summary["arms"].items():
        post = metrics["post"]
        print(f"{arm:<16} {'T1':<4} {post['wins']:>5} {post['rate']:>6.3f} "
              f"{post.get('brier', 0):>6.3f} {post.get('ece', 0):>6.3f} "
              f"{post['mean_tokens']:>7}")


def build_summary(sets, arms):
    baseline = {form: load_rows(OUT / "baseline" / form) for form in FORMS}
    for form, rows in baseline.items():
        if len(rows) != len(sets[form]) or not all(row.get("done") for row in rows):
            raise SystemExit(f"Baseline {form} is incomplete; run --stage baseline first.")
    summary = dict(sets={name: set_info(name, cases) for name, cases in sets.items()},
                   baseline={form: row_metrics(rows) for form, rows in baseline.items()},
                   arms={})
    for arm in arms:
        post = load_rows(OUT / "post" / arm / "T1")
        if len(post) != len(sets["T1"]) or not all(row.get("done") for row in post):
            raise SystemExit(f"Post-test for {arm} is incomplete; run --stage post first.")
        lesson_path = OUT / "arms" / arm / "lesson.txt"
        reflection_path = OUT / "arms" / arm / "reflection.txt"
        post_metrics = row_metrics(post)
        summary["arms"][arm] = dict(
            lesson_words=len(lesson_path.read_text(encoding="utf-8").split())
            if lesson_path.exists() else 0,
            lesson=lesson_path.read_text(encoding="utf-8") if lesson_path.exists() else "",
            reflection=reflection_path.read_text(encoding="utf-8")
            if reflection_path.exists() else "",
            post=post_metrics,
            delta_vs_baseline_T1=round(
                post_metrics["rate"] - summary["baseline"]["T1"]["rate"], 3),
            paired_vs_baseline_T1=paired(baseline["T1"], post))
    save(OUT / "summary.json", summary)
    write_rows_csv(baseline, arms)
    print_table(summary)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", default="all",
                        choices=("all", "sets", "baseline", "teach", "lesson", "post",
                                 "reflect", "summary"))
    parser.add_argument("--arms", nargs="+", default=list(ARMS), choices=ARMS)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    sets = load_sets()
    write_sets(sets)
    if args.stage == "sets":
        print(json.dumps({name: set_info(name, cases) for name, cases in sets.items()},
                         indent=2))
        return
    if args.stage in ("all", "baseline"):
        for form in FORMS:
            parallel(lambda case: baseline_job(form, case), sets[form], args.workers)
    if args.stage in ("all", "teach"):
        if any(arm in args.arms for arm in ("taught", "teacher_lesson")):
            parallel(teach_guided, sets["train"], args.workers)
        if "practice" in args.arms:
            parallel(teach_practice, sets["train"], args.workers)
    if args.stage in ("all", "lesson"):
        write_lessons(sets, args.arms)
    if args.stage in ("all", "post"):
        for arm in args.arms:
            parallel(lambda case: post_job(arm, case), sets["T1"], args.workers)
    if args.stage in ("all", "reflect"):
        for arm in args.arms:
            run_reflect(arm, sets["T1"])
    if args.stage in ("all", "summary"):
        build_summary(sets, args.arms)


if __name__ == "__main__":
    main()
