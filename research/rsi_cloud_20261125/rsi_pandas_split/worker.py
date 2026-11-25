"""Version-isolated functional pandas report: edit an attached selection or an independent draft."""
import json,sys,warnings
import pandas as pd
import numpy as np

def run(q):
    attached,style,width,seed,method=q
    df=pd.DataFrame({'qty':[8+seed,9+seed,12+seed]+[19+seed]*(width-3)})
    if pd.__version__.startswith('2.'):
        pd.options.mode.copy_on_write=False  # documented legacy default
    selected=df['qty'] if style==0 else df.loc[:,'qty']
    if not attached:selected=selected.copy(deep=True)
    before=(list(map(int,df['qty'])),list(map(int,selected)),str(selected.dtype))
    shared=bool(np.shares_memory(df['qty'].to_numpy(copy=False),selected.to_numpy(copy=False)))
    qty=20+seed
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        selected.iloc[0]=qty
        if method=='both':df.loc[0,'qty']=qty
    after=(list(map(int,df['qty'])),list(map(int,selected)))
    return {'before':before,'after':after,'shared':shared,'version':pd.__version__}

if __name__=='__main__':
    for q in json.load(sys.stdin):
        print(json.dumps(run(q)))
