"""Visualize AI-generated Q2 candidates; requires q2_candidate_models.py outputs."""
import csv, hashlib, json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[2]
GRID=ROOT/'results/q2/fidelity_grid.csv'
SUMMARY=ROOT/'experiments/reports/q2_2_descriptive_summary.csv'
OUT=ROOT/'figures/q2/q2_candidates.png'
with GRID.open(encoding='utf-8',newline='') as f: grid=list(csv.DictReader(f))
with SUMMARY.open(encoding='utf-8',newline='') as f: summary=list(csv.DictReader(f))
fig,axes=plt.subplots(1,3,figsize=(13,4.5),sharey=True,layout='constrained')
for ax,call,label in zip(axes,('flat','mod','tv'),('Flat','Modulated','Two-voice')):
    for method,color in [('isotonic','#0072B2'),('exponential','#D55E00')]:
        rows=[r for r in grid if r['call_type']==call and r['scenario']==method+'_equal']
        if len(rows)!=253:raise ValueError('Missing candidate grid')
        ax.plot([float(r['distance_m']) for r in rows],[float(r['estimate']) for r in rows],label=method.title(),color=color)
    ds=[4,8,16,32,64,128,256]; means=[]
    for d in ds:
        subset=[float(r['mean']) for r in summary if r['call_type']==call and int(r['distance_m'])==d]
        if len(subset)!=3:raise ValueError('Missing descriptive group')
        means.append(sum(subset)/3)
    ax.scatter(ds,means,color='#222222',s=18,zorder=3,label='Observed equal-weight mean')
    for threshold in (.3,.7):ax.axhline(threshold,color='#888888',ls='--',lw=.7)
    ax.set(xlim=(0,260),ylim=(0,1),title=label,xlabel='Distance (m)')
    ax.grid(alpha=.18)
axes[0].set_ylabel('Composite correlation (equal weights)')
axes[0].legend(fontsize=7,loc='lower left')
fig.suptitle('Exploratory AI-generated candidates — not team-reviewed',fontweight='bold')
OUT.parent.mkdir(parents=True,exist_ok=True);fig.savefig(OUT,dpi=200);plt.close(fig)
meta={'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
      'grid_sha256':hashlib.sha256(GRID.read_bytes()).hexdigest(),
      'summary_sha256':hashlib.sha256(SUMMARY.read_bytes()).hexdigest(),
      'matplotlib':matplotlib.__version__,'status':'AI-generated candidate; no confidence interval'}
(ROOT/'experiments/reports/q2_candidate_plot_metadata.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
