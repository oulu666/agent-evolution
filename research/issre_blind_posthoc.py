"""After unsealing only. Recheck targeted functional behavior and time actual frozen plans."""
import json
import random
import subprocess
import sys
import tempfile
from io import BytesIO
from pathlib import Path
from statistics import median
from time import perf_counter_ns
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from issre_blind_frame import OUT, git, persist
from issre_blind_tasks import RUN, observe, tasks
from issre_blind_run import FILES, digest


def read(name):
    return json.loads((OUT / name).read_text(encoding="utf8"))


def click_witness(i):
    import click
    from click.testing import CliRunner
    if i == 4:
        class TestType(click.ParamType):
            pass
        return TestType().to_info_dict()["name"]
    if i == 1:
        @click.command()
        @click.option("--upper", flag_value="upper", envvar="UPPER")
        def cli(upper):
            click.echo(upper)
        r = CliRunner().invoke(cli, [], env={"UPPER": "whatever"})
        return [r.exit_code, r.output.strip()]
    if i == 2:
        closed = []
        def on_option(ctx, param, value):
            ctx.call_on_close(lambda: closed.append("closed"))
            ctx.exit()
        @click.command()
        @click.option("--finish", is_flag=True, is_eager=True, callback=on_option)
        def cli(finish):
            pass
        r = CliRunner().invoke(cli, ["--finish"])
        return [r.exit_code, closed]
    if i == 3:
        @click.command()
        @click.option("-g", type=click.Choice(["foo","bar"]), show_choices=False)
        def cli(g):
            pass
        r = CliRunner().invoke(cli, ["--help"])
        return [r.exit_code, "[TEXT]" in r.output]
    @click.command(context_settings={"show_default": True})
    @click.option("--n", default=1, show_default=False)
    def cli(n):
        pass
    r = CliRunner().invoke(cli, ["--help"])
    return [r.exit_code, "--n" in r.output, "default:" in r.output.lower()]


def witness(p, i):
    if p == "click":
        return click_witness(i)
    if p == "markdown":
        if i == 2:
            return None
        from markdown import Markdown
        dest = BytesIO()
        Markdown().convertFile(input=BytesIO(b"foo"), output=dest)
        return dest.getvalue().decode()
    from tqdm import tqdm
    class WriteOnly:
        def __init__(self):
            self.parts = []
        def write(self, text):
            self.parts.append(text)
    stream = WriteOnly()
    previous = sys.stderr
    try:
        sys.stderr = stream
        with tqdm(total=1, file=stream, ascii=True, disable=False, bar_format="{n}/{total}") as bar:
            bar.update()
        return [bar.n, "1/1" in "".join(stream.parts)]
    finally:
        sys.stderr = previous


def benchmark(p):
    plans = read("schedules.json")[p]
    byname = {t.name:t for t in tasks(p)}
    cases = [(r,m,v["inputs"]) for r,methods in plans.items() for m,v in methods.items()]
    for r in plans:
        cases.append((r,"Joint inputs, full fields",{
            n:list(byname[n].expected) for n in plans[r]["Joint"]["inputs"]}))
    times = {r:{m:[] for rr,m,_ in cases if rr == r} for r in plans}
    rng = random.Random(623)
    for trial in range(8):
        rng.shuffle(cases)
        for r,m,inputs in cases:
            start = perf_counter_ns()
            for n,fields in inputs.items():
                a = RUN[p](n)
                vals = {f:observe(p,n,a,f) for f in fields}
                if any(vals[f] != byname[n].expected[f] for f in fields):
                    raise ValueError(("unexpected replay", p,n,vals))
            elapsed = perf_counter_ns()-start
            if trial:
                times[r][m].append(elapsed)
    return times


def main():
    for name,h in read("freeze.json")["files"].items():
        if digest((HERE if name in FILES else OUT)/name) != h:
            raise RuntimeError("freeze mismatch: "+name)
    results = []
    for row in read("paired.json"):
        p, i = row["project"],row["id"]
        entry = {"project":p,"id":i,"commit":row["commit"]}
        for side in ["parent","commit"]:
            pkg = "src/click" if p=="click" else p
            archive = git(p,"archive","--format=zip",row[side],pkg)
            with tempfile.TemporaryDirectory() as tmp:
                with ZipFile(BytesIO(archive)) as z:
                    z.extractall(tmp)
                proc = subprocess.run([sys.executable,"-I",__file__,"worker",p,str(i),tmp],
                    check=True,capture_output=True,encoding="utf8",timeout=120)
                entry[side+"_data"] = json.loads(proc.stdout)
        results.append(entry)
    persist(OUT/"posthoc_and_costs.json",results)


if __name__ == "__main__":
    if len(sys.argv)==1:
        main()
    else:
        _,_,project,num,root = sys.argv
        directory = Path(root)
        sys.path[:0] = [str(directory/"src"),str(directory)]
        assert Path(__import__(project).__file__).resolve().is_relative_to(directory)
        plan_times = benchmark(project)
        try:
            case_result = witness(project,int(num))
        except Exception as exc:
            case_result = {"exception":type(exc).__name__,"detail":str(exc)}
        print(json.dumps({"witness":case_result,"plan_ns":plan_times}))
