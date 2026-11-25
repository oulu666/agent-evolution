"""Plot exact detection attribution as a function of call allowance."""
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from empirical_sqlite import OUT


def main():
    tables=json.loads((OUT/'budget_matrix.json').read_text())
    panels=[('inventory','saved','Inventory / saved'),('inventory','construct','Inventory / constructible'),
            ('sqlite','basic','SQLite / basic'),('sqlite','extended','SQLite / extended')]
    colors=('#137572','#78c7b4','#f4bc66','#686d85')
    fields=('hit','miss','budget','permission')
    fig,axes=plt.subplots(2,2,figsize=(9,6.2),sharey=True,layout='constrained')
    for ax,(env,perm,title) in zip(axes.flat,panels):
        rr=[r for r in tables[env] if r['method']=='ABA' and r['perm']==perm]
        total=sum(rr[0][f] for f in fields)
        for r in rr:
            height=0
            for key,color in zip(fields,colors):
                n=100*r[key]/total
                ax.bar(r['B'],n,bottom=height,color=color,width=.68)
                height+=n
        ax.set_title(f'{title}  (n={total})',loc='left',fontsize=11)
        ax.set_xticks([2,3,4,5])
        ax.set_ylim(0,100)
        ax.spines[['top','right']].set_visible(False)
    for ax in axes[-1]:
        ax.set_xlabel('Maximum calls per session')
    for ax in axes[:,0]:
        ax.set_ylabel('Share of fault cases (%)')
    fig.legend(handles=[Patch(color=c,label=t) for c,t in zip(colors,
        ('Detected','Reachable but missed','More calls required','Access blocked'))],
        loc='outside lower center',ncol=4,fontsize=9)
    fig.savefig(OUT/'budget_attribution.png',dpi=200)


if __name__=='__main__':
    main()
