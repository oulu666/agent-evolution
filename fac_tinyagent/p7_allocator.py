"""Measured local-response selector. Accepts development losses only.

This implements the frozen P7 value rule, not a full production replay scheduler.
No skill-specific preferences, holdout outcomes, or fitted saturation terms.
"""
from __future__ import annotations
import math
from statistics import mean

def macro_loss(rows):
    skills=sorted({r['skill'] for r in rows})
    if not skills: raise ValueError('Empty response set')
    value=mean(mean(float(r['nll']) for r in rows if r['skill']==s) for s in skills)
    if not math.isfinite(value): raise ValueError('Nonfinite response loss')
    return value

def select_action(control_dev, action_dev, replay_input_tokens):
    """Rank finite-step gains versus a same-step background control, per token.

    All actions must be independent branches from the same optimizer state.
    A negative best value remains reported as negative, not a promised benefit.
    """
    expected={(r['id'],r['skill']) for r in control_dev}
    base=macro_loss(control_dev);values={}
    for action,rows in action_dev.items():
        if {(r['id'],r['skill']) for r in rows}!=expected:
            raise ValueError('Responses must use the identical development set')
        cost=replay_input_tokens[action]
        if cost<=0:raise ValueError('Cost must be positive')
        gain=base-macro_loss(rows)
        values[action]={'macro_nll_gain':gain,'input_tokens':cost,'value_per_token':gain/cost}
    if not values:raise ValueError('No measured actions')
    best=max(sorted(values),key=lambda k:values[k]['value_per_token'])
    return {'action':best,'positive_gain':values[best]['value_per_token']>0,'values':values,'signal':'measured development macro NLL reduction versus background / replay input tokens'}
