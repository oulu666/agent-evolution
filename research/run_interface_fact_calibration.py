"""Independent positive/negative controls for the frozen fact reader."""
import json
from pathlib import Path
from run_interface_fact_readout import read_fact, OUT as FIRST
from run_interface_boundaries import WORLDS, iso, execute
from run_rsi_operator_memory import FrozenAgent, ROOT

OUT=ROOT/'runs_rsi_interface_fact_calibration_20261123'


def save(name,obj):
    path=OUT/name
    tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(obj,indent=2))
    tmp.replace(path)


def present(view,days,records,returned):
    if view=='archived':
        probe=dict(known_event_dates=days,start=days[0],end=days[-1],returned_dates=[r['date'] for r in returned])
        return 'calendar_range calibration, one known event on each calibration date. '+json.dumps(probe)
    def pack(rs):
        return [dict(stamp=r['date'],uid=r['id']) for r in rs]
    probe=dict(api='agenda_window',known_records=pack(records),request=dict(lo_day=days[0],hi_day=days[-1]),returned_records=pack(returned))
    return 'Date-window calibration. lo_day is the lower date and hi_day the upper date; inclusion is undocumented. '+json.dumps(probe)


def events(start):
    days=[iso(start,i) for i in range(3)]
    return days,[dict(date=d,id='E'+d.replace('-','')) for d in days]


def main():
    OUT.mkdir(exist_ok=True)
    if (OUT/'summary.json').exists():
        print((OUT/'summary.json').read_text());return
    unseen=['2052-11-30','2080-02-28']
    save('protocol.json',dict(control_date='2050-07-10',unseen=unseen,
         controls='two constructed observations per format, same length; left+middle versus middle+right',
         rule='per format and endpoint choose closest anchor margin; tie absent; no refit',
         weight_updates=0,comparison='same fresh logits with prior zero threshold'))
    agent=FrozenAgent()
    controls={}
    ds,rs=events('2050-07-10')
    for view in ('archived','renamed'):
        anchors=[]
        for selected in (rs[:2],rs[1:]):
            ctx=present(view,ds,rs,selected)
            anchors.append([read_fact(agent,ctx,ds[i]) for i in (0,2)])
        controls[view]=dict(raw=anchors,positive=[anchors[0][0]['mean_margin'],anchors[1][1]['mean_margin']],
                            negative=[anchors[1][0]['mean_margin'],anchors[0][1]['mean_margin']])
    save('frozen_anchors.json',controls)
    anchors=json.loads((OUT/'frozen_anchors.json').read_text())
    bindings=[]
    for view,ctrl in anchors.items():
        for start in unseen:
            ds,rs=events(start)
            for name,contract in WORLDS.items():
                seen=execute(rs,contract,ds[0],ds[-1])
                ctx=present(view,ds,rs,seen)
                facts=[read_fact(agent,ctx,d) for d in (ds[0],ds[-1])]
                calibrated=[abs(b['mean_margin']-ctrl['positive'][i]) < abs(b['mean_margin']-ctrl['negative'][i]) for i,b in enumerate(facts)]
                bindings.append(dict(view=view,start=start,world=name,seen=seen,facts=facts,zero=[b['predicted'] for b in facts],calibrated=calibrated))
    save('frozen_choices.json',bindings)
    totals={}; deployed=[]
    prior_calls=json.loads((FIRST/'deployment.json').read_text())
    for row in json.loads((OUT/'frozen_choices.json').read_text()):
        view=row['view']; world=row['world']; truth=WORLDS[world]
        fixture=json.loads((FIRST/(view+'_fixture.json')).read_text())
        days=[r['day'] for r in prior_calls if r['view']==view and r['world']==world and r['arm']=='direct']
        for arm in ('zero','calibrated'):
            bits=row[arm]
            tally=totals.setdefault(view,{}).setdefault(arm,dict(bits=0,mappings=0,days=0))
            tally['bits']+=sum(a==b for a,b in zip(bits,truth))
            tally['mappings']+=tuple(bits)==truth
            for d in days:
                low,high=iso(d,0 if bits[0] else -1),iso(d,0 if bits[1] else 1)
                got=execute(fixture,truth,low,high)
                expected=[e for e in fixture if e['date']==d]
                tally['days']+=got==expected
                deployed.append(dict(view=view,start=row['start'],world=world,arm=arm,day=d,low=low,high=high,got=got,expected=expected))
    save('deployment.json',deployed)
    save('summary.json',dict(totals=totals,model_calls=agent.calls,fresh_probes=len(bindings),constructed_controls=4))
    print(totals,flush=True)


if __name__=='__main__':
    main()
