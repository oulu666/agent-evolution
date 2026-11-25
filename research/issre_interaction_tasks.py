"""Two-factor documentation tasks. Each public target operation returns JSON-safe evidence."""
from calendar import monthrange
from datetime import datetime, timedelta

FAMILIES = {
    "attrs": ["convert_validate","private_evolve","nested_dict","compare","defaults","assignment"],
    "dateutil": ["month_shift","weekday","monthly","weekly","parse_defaults","parse_offset"],
}
FACTORS = {
    "convert_validate": ["convert string to int","validate post-conversion type"],
    "private_evolve": ["private attribute","slotted class"],
    "nested_dict": ["nested attrs object","exclude metadata field"],
    "compare": ["exclude field from equality","change this field"],
    "defaults": ["list factory default","explicit constructor value"],
    "assignment": ["convert on assignment","validate on assignment"],
    "month_shift": ["start on day 31","target leap February"],
    "weekday": ["set day to first of month","use second Monday"],
    "monthly": ["start on day 31","step every two months"],
    "weekly": ["interval two","select two weekdays"],
    "parse_defaults": ["leap year in default","default day exceeds February length"],
    "parse_offset": ["supply numeric time zone","ignore time zone"],
}
CELLS = ["00","10","01","11"]


def attrs_task(name, a, b):
    import attr
    if name == "convert_validate":
        @attr.s
        class Item:
            value = attr.ib(converter=int if a else None,
                            validator=attr.validators.instance_of(int) if b else None)
        expected = "TypeError" if b and not a else ([7,"int"] if a else ["7","str"])
        try:
            value = Item("7").value
        except TypeError:
            return "TypeError", expected
        return [value,type(value).__name__], expected
    if name == "private_evolve":
        field = "_x" if a else "x"
        item = attr.make_class("Item",{field:attr.ib()},slots=b)(1)
        changed = attr.evolve(item,x=3)
        return [getattr(changed,field),getattr(item,field)], [3,1]
    if name == "nested_dict":
        @attr.s
        class Item:
            x = attr.ib()
            note = attr.ib(default="note")
        value = Item(Item(2) if a else 2)
        fields = attr.asdict(value,filter=(lambda field,v: field.name!="note") if b else None)
        expected = {"x":2}
        if not b:
            expected["note"] = "note"
        outer = dict(expected)
        if a:
            outer["x"] = expected
        return fields,outer
    if name == "compare":
        @attr.s
        class Item:
            x = attr.ib()
            detail = attr.ib(eq=not a)
        left, right = Item(1,2), Item(1,3 if b else 2)
        return left==right, a or not b
    if name == "defaults":
        @attr.s
        class Item:
            value = attr.ib(factory=list) if a else attr.ib(default=None)
        item = Item([4]) if b else Item()
        return item.value, [4] if b else ([] if a else None)
    @attr.define
    class Item:
        value: object = attr.field(converter=int if a else None,
            validator=attr.validators.instance_of(int) if b else None)
    item = Item(1)
    expected = ["TypeError",1] if b and not a else ([9,"int"] if a else ["9","str"])
    try:
        item.value = "9"
    except TypeError:
        return ["TypeError",item.value], expected
    return [item.value,type(item.value).__name__], expected


def date_task(name, a, b):
    from dateutil import parser
    from dateutil.relativedelta import relativedelta, MO
    from dateutil.rrule import rrule, MONTHLY, WEEKLY, MO as MON, WE
    if name == "month_shift":
        year = 2020 if b else 2021
        day = 31 if a else 15
        got = datetime(year,1,day) + relativedelta(months=1)
        expected = datetime(year,2,min(day,monthrange(year,2)[1]))
    elif name == "weekday":
        start = datetime(2021,3,17)
        got = start + relativedelta(day=1 if a else None,weekday=MO(2 if b else 1))
        expected = datetime(2021,3,(1 if a else 22)+(7 if b else 0))
    elif name == "monthly":
        day = 31 if a else 15
        step = 2 if b else 1
        got = list(rrule(MONTHLY,dtstart=datetime(2021,1,day),count=4,interval=step))
        valid_months = [m for m in range(1,13,step) if monthrange(2021,m)[1]>=day][:4]
        return [v.isoformat() for v in got],[datetime(2021,m,day).isoformat() for m in valid_months]
    elif name == "weekly":
        step = 2 if a else 1
        start = datetime(2021,3,1)
        got = list(rrule(WEEKLY,dtstart=start,count=4,interval=step,byweekday=(MON,WE) if b else MON))
        offsets = [7*step*w+d for w in range(4) for d in ([0,2] if b else [0])][:4]
        return [v.isoformat() for v in got],[(start+timedelta(days=i)).isoformat() for i in offsets]
    elif name == "parse_defaults":
        year = 2020 if a else 2021
        day = 31 if b else 10
        got = parser.parse("February",default=datetime(year,1,day,9,45))
        expected = datetime(year,2,min(monthrange(year,2)[1],day),9,45)
    else:
        got = parser.parse("2021-04-05 12:30"+(" +0530" if a else ""),ignoretz=b)
        return got.isoformat(), "2021-04-05T12:30:00"+("+05:30" if a and not b else "")
    return got.isoformat(),expected.isoformat()


def execute(p, name, cell):
    a,b = (v=="1" for v in cell)
    try:
        actual,expected = (attrs_task if p=="attrs" else date_task)(name,a,b)
        return {"value":actual,"expected":expected,"pass":actual==expected}
    except Exception as error:
        return {"exception":type(error).__name__,"pass":False}


def menus(p):
    plans = {m:[] for m in ("single","combined","mirror","ordinary","all_basic","all")}
    for i,name in enumerate(FAMILIES[p]):
        first, second = ("10","01") if i%2==0 else ("01","10")
        for method,cells in (("single",["10","01"]),("combined",[first,"11"]),
                ("mirror",[second,"11"]),("ordinary",["00"]),("all_basic",CELLS[:3]),("all",CELLS)):
            plans[method].extend((name,c) for c in cells)
    return plans
