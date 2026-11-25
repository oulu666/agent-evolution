"""Human reference based on old public documentation, prepared before inspecting extraction."""
from functools import partial

GOLD = {
    "transitions":["machine.prepare_event","transition.prepare","transition.conditions","transition.unless",
        "machine.before_state_change","transition.before","state.on_exit","state.on_enter",
        "transition.after","machine.after_state_change","machine.finalize_event"],
    "statemachine":["validators()","conditions()","unless()","before_transition()","before_<event>()",
        "on_exit_state()","on_exit_<state.id>()","on_transition()","on_<event>()","on_enter_state()",
        "on_enter_<state.id>()","after_<event>()","after_transition()"],
}


def transitions_run():
    from transitions import Machine
    log = []
    def mark(name,answer=None):
        log.append(name)
        return answer
    events = {name:partial(mark,name) for name in GOLD["transitions"]}
    m = Machine(states=[dict(name="a",on_exit=events["state.on_exit"]),
                        dict(name="b",on_enter=events["state.on_enter"])],initial="a",
        auto_transitions=False,prepare_event=events["machine.prepare_event"],
        before_state_change=events["machine.before_state_change"],after_state_change=events["machine.after_state_change"],
        finalize_event=events["machine.finalize_event"])
    m.add_transition("advance","a","b",prepare=events["transition.prepare"],
        conditions=partial(mark,"transition.conditions",True),unless=partial(mark,"transition.unless",False),
        before=events["transition.before"],after=events["transition.after"])
    log.clear()
    m.advance()
    return dict(end=m.state,trace=log)


def statemachine_run():
    from statemachine import StateMachine,State
    log = []
    class Demo(StateMachine):
        a = State(initial=True)
        b = State(final=True)
        advance = a.to(b,validators="validate",cond="allow",unless="block")
        def validate(self): log.append("validators()")
        def allow(self):
            log.append("conditions()")
            return True
        def block(self):
            log.append("unless()")
            return False
        def before_transition(self): log.append("before_transition()")
        def before_advance(self): log.append("before_<event>()")
        def on_exit_state(self): log.append("on_exit_state()")
        def on_exit_a(self): log.append("on_exit_<state.id>()")
        def on_transition(self): log.append("on_transition()")
        def on_advance(self): log.append("on_<event>()")
        def on_enter_state(self): log.append("on_enter_state()")
        def on_enter_b(self): log.append("on_enter_<state.id>()")
        def after_advance(self): log.append("after_<event>()")
        def after_transition(self): log.append("after_transition()")
    m = Demo()
    # Initial entry may be deferred by a runtime. Read the initial state before measuring the event.
    initial = m.current_state_value
    log.clear()
    m.advance()
    return dict(initial=initial,end=m.current_state_value,trace=log)

