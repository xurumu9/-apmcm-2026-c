"""Q2 missing-value stress tests and weight-scenario figure; not confidence intervals."""
from __future__ import annotations
import csv, hashlib, json, platform
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import q2_candidate_models as model

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / 'experiments/reports'
MISSING = REPORT / 'q2_missingness_extremes.csv'
WEIGHTS = REPORT / 'q2_candidate_weight_sensitivity.csv'

def main():
    with MISSING.open(encoding='utf-8',newline='') as f: rows=list(csv.DictReader(f))
    grouped={(r['call_type'],int(r['distance_m'])):r for r in rows}
    expected={(c,int(d)) for c in model.CALLS for d in model.DIST}
    if len(rows)!=21 or set(grouped)!=expected:raise ValueError('Expected 21 unique missingness groups')
    grid=np.linspace(4,256,2521); out=[]
    for call in model.CALLS:
        vals=[grouped[(call,int(d))] for d in model.DIST]
        lower=np.array([float(r['min_if_missing_zero']) for r in vals])
        upper=np.array([float(r['max_if_missing_one']) for r in vals])
        if np.any(lower>upper):raise ValueError('Invalid extreme inputs')
        lowcurve=model.predict('isotonic',model.DIST,lower,grid)
        highcurve=model.predict('isotonic',model.DIST,upper,grid)
        if np.any(lowcurve>highcurve+1e-12):raise ValueError('Extreme fits out of order')
        for threshold,state in model.LEVELS:
            low,ls=model.crossing(grid,lowcurve,threshold)
            high,hs=model.crossing(grid,highcurve,threshold)
            out.append([call,threshold,state,low,ls,high,hs,'all_missing_0_vs_1_assumption_not_confidence_interval'])
    path=REPORT/'q2_missingness_distance_stress.csv'
    with path.open('w',encoding='utf-8',newline='') as f:
        w=csv.writer(f,lineterminator='\n');w.writerow(['call_type','threshold','state','zero_scenario_m','zero_status','one_scenario_m','one_status','interpretation']);w.writerows(out)
    with WEIGHTS.open(encoding='utf-8',newline='') as f: records=list(csv.DictReader(f))
    labels=('Equal','Spectrogram\npriority','Spectrum\npriority','Envelope\npriority')
    names=('equal','spectrogram_priority','spectrum_priority','envelope_priority')
    fig,axes=plt.subplots(1,3,figsize=(13,4.4),sharey=True,layout='constrained')
    for ax,call in zip(axes,model.CALLS):
        for j,(th,color) in enumerate(((.3,'#0072B2'),(.5,'#D55E00'),(.7,'#009E73'))):
            y=[];censored=[]
            for i,name in enumerate(names):
                found=[r for r in records if r['call_type']==call and r['scenario']=='isotonic_'+name and float(r['threshold'])==th]
                if len(found)!=1:raise ValueError('Missing or duplicate weight scenario')
                r=found[0]
                if r['status']=='within_range':y.append(float(r['radius_m']))
                elif r['status']=='at_least_256m':y.append(np.nan);censored.append(i)
                else:raise ValueError('Figure does not support this boundary; update figure before drawing')
            ax.plot(range(4),y,marker='o',color=color,label=f'Threshold {th}')
            for i in censored:ax.scatter([i],[256],marker='^',color=color,s=65,zorder=5)
        ax.set_title({'flat':'Flat','mod':'Modulated','tv':'Two-voice'}[call]);ax.set_xticks(range(4),labels,fontsize=8)
        ax.set_ylim(0,270);ax.grid(axis='y',alpha=.2)
    axes[0].set_ylabel('Estimated distance (m)')
    axes[0].legend(fontsize=8,loc='upper left')
    fig.suptitle('AI candidate: weight sensitivity (triangle = threshold met at 256 m)',fontsize=12,weight='bold')
    p=ROOT/'figures/q2/q2_weight_sensitivity.png';p.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(p,dpi=200);plt.close(fig)
    meta={'run_id':'q2_sensitivity_review_v1','python':platform.python_version(),'numpy':np.__version__,'matplotlib':matplotlib.__version__,
          'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'model_script_sha256':hashlib.sha256(Path(model.__file__).read_bytes()).hexdigest(),
          'input_missing_sha256':hashlib.sha256(MISSING.read_bytes()).hexdigest(),
          'input_weights_sha256':hashlib.sha256(WEIGHTS.read_bytes()).hexdigest(),
          'random_seed':None,'interval':'deterministic stress scenarios; not confidence interval',
          'status':'AI-generated, not team-reviewed'}
    (REPORT/'q2_sensitivity_review_metadata.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
    print('Generated 9 missingness stress cases and one weight-sensitivity figure.')

if __name__=='__main__':main()
