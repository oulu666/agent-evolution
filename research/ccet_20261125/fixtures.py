"""Typed public operations. Only (broad class, operation, representation) reaches the planner."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Item:
    args: tuple
    signature: tuple
    expected: object
    prompt: str


VERSIONS = {"packaging": ("23.2", "25.0"), "tabulate": ("0.8.10", "0.9.0")}


def menu(tool, n):
    if tool == "packaging":
        cases = [
            (f">={n}.0", f"{n}.2", False, True, (0, "lower", "release")),
            (f"=={n}.0", f"{n}.1", False, False, (0, "equal", "release")),
            (f">={n}.0", f"{n}.1rc1", True, True, (1, "lower", "pre")),
            (f"<{n}.0", f"{n}.0rc1", True, False, (1, "upper", "pre")),
            (f">{n}.0", f"{n}.0.post1", True, False, (1, "lower", "post")),
            (f"=={n}.0", f"{n}.0+local", False, True, (1, "equal", "local")),
        ]
        return [Item((s,v,p),sig,y,f"Check if release {v} satisfies {s}, allow prereleases={p}.")
                for s,v,p,y,sig in cases]
    cases = [
        (str(n), "text", str(n), (0,"text","digits")),
        ("ID"+str(n), "text", "ID"+str(n), (0,"text","label")),
        (f"{n:04d}", "text", f"{n:04d}", (1,"text","padded")),
        (f"{n}.00", "text", f"{n}.00", (1,"text","decimal")),
        (float(n)+.5, "decimal", f"{n}.50", (1,"number","decimal")),
        (1000*n+7, "group", f"{1000*n+7:,}", (1,"number","digits")),
    ]
    return [Item((v,mode),sig,y,f"Render a one-cell TSV report for {v!r}, display mode {mode}.")
            for v,mode,y,sig in cases]


def execute(tool, args, altered=False, fallback=False):
    if tool == "packaging":
        if fallback:
            from pip._vendor.packaging.specifiers import SpecifierSet
        else:
            from packaging.specifiers import SpecifierSet
        spec,version,pre=args
        return SpecifierSet(spec).contains(version, prereleases=False if altered and not fallback else pre)
    value,mode=args
    if fallback:
        from io import StringIO
        import csv
        buf=StringIO()
        cell={"text":lambda: str(value),"decimal":lambda:format(value,".2f"),"group":lambda:format(value,",d")}[mode]()
        csv.writer(buf,delimiter="\t",lineterminator="\n").writerow([cell])
        return buf.getvalue().rstrip("\n")
    from tabulate import tabulate
    options = {"text":{"disable_numparse":not altered},"decimal":{"floatfmt":".2f"},"group":{"intfmt":","}}
    return tabulate([[value]],tablefmt="tsv",**options[mode]).strip()

