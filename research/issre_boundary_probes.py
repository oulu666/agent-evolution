"""Public-API fixtures that compile extracted clause slots into stimuli and observations."""
import asyncio


def blinker_case(rule, varied, watch):
    from blinker import ANY, Signal
    signal = Signal()
    sender = object()
    binding = sender if varied else ANY
    weak = not varied
    arguments = {"n":37,"label":"test"} if varied else {}
    seen = []
    def receiver(source, **kw):
        if watch and rule["kind"]=="forward":
            seen.append([source is sender,kw])
        return 9
    if rule["kind"]=="notification":
        def log(source, **kwargs):
            values = {"receiver":receiver,"sender":binding,"weak":weak}
            seen.append([source is signal, [k in kwargs and kwargs[k] is values[k] for k in rule["fields"]]])
        action = rule["action"]
        if action=="disconnect":
            signal.connect(receiver,sender=binding,weak=weak)
        if watch:
            getattr(signal,rule["observer"]).connect(log,weak=False)
        opts = {"sender":binding}
        if action=="connect":
            opts["weak"]=weak
        getattr(signal,action)(receiver,**opts)
        # The end-state readout is shared with the ordinary tests.
        deliveries = signal.send(sender)
        return ([v for _,v in deliveries], [9] if action=="connect" else [],
                seen, [[True,[True]*len(rule["fields"])]], 2+int(action=="disconnect")+int(watch))
    async def async_receiver(source, **kw):
        return receiver(source,**kw)
    asynchronous = rule["action"]=="send_async"
    callback = async_receiver if asynchronous else receiver
    signal.connect(callback,sender=binding,weak=weak)
    send = getattr(signal,rule["action"])
    deliveries = asyncio.run(send(sender,**arguments)) if asynchronous else send(sender,**arguments)
    return ([[fn is callback,val] for fn,val in deliveries],[[True,9]],
            seen,[[True,arguments]],2)


def pluggy_case(rule, varied, watch):
    import pluggy
    pm = pluggy.PluginManager("boundary")
    spec = pluggy.HookspecMarker("boundary")
    impl = pluggy.HookimplMarker("boundary")
    kind = rule["kind"]
    val = 37 if varied else 7
    seen = []
    class Spec:
        @spec(historic=kind=="deferred")
        def probe(value):
            """Return a fixed marker."""
    class Plugin:
        @impl
        def probe(self,value):
            if watch and kind=="monitor":
                seen.append(["impl",value])
            return 9
    pm.add_hookspecs(Spec)
    caller = pm.hook.probe
    if kind=="deferred":
        result_callback = (lambda result: seen.append(result)) if watch else None
        if not varied:
            pm.register(Plugin())
        result = getattr(caller,rule["action"])(**{rule["observer"]:result_callback,"kwargs":{"value":val}})
        if varied:
            pm.register(Plugin())
        return result,None,seen,[9],3
    pm.register(Plugin())
    if kind=="temporary":
        def extra(value):
            if watch:
                seen.append(value)
            return 13
        def other(value):
            if watch:
                seen.append(value)
            return 17
        extras = [extra,other] if varied else [extra]
        both = getattr(caller,rule["action"])(extras,{"value":val})
        after = caller(value=val)
        markers = [9,13,17] if varied else [9,13]
        return [sorted(both),after],[markers,[9]],seen,[val]*len(extras),4
    def before(name,impls,kwargs):
        if watch:
            seen.append(["before",kwargs["value"]])
    def after(outcome,name,impls,kwargs):
        if watch:
            seen.append(["after",kwargs["value"],outcome.get_result()])
    undo = getattr(pm,rule["action"])(before,after)
    result = caller(value=val)
    expected_trace = [["before",val],["impl",val],["after",val,[9]]]
    if varied:
        undo()
        result = [result,caller(value=val+1)]
        expected_trace.append(["impl",val+1])
    return result,[[9],[9]] if varied else [9],seen,expected_trace,6 if varied else 4


def execute(p,rule,varied,mode):
    watch = mode!="final"
    try:
        f,ef,b,eb,calls = (blinker_case if p=="blinker" else pluggy_case)(rule,varied,watch)
    except Exception as e:
        return {"ok":False,"error":type(e).__name__,"detail":str(e)[:200]}
    return {"ok":(mode=="boundary" or f==ef) and (not watch or b==eb),
            "end":f,"expected_end":ef,"trace":b if watch else None,"expected_trace":eb if watch else None,
            "public_calls":calls}

