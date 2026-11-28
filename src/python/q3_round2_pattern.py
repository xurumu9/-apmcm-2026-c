"""R2-2: fixed-C1 matched reference contrasts; no classifier search."""
import json
import hashlib
import platform
import subprocess
import warnings
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
import sklearn
from threadpoolctl import threadpool_limits
from q3_playback_analysis import ROOT, INPUT, COLS, COMBOS, TYPES, fit_combo, predict_combo, combo, plt
from q3_uncertainty_delivery import load_data, resample, SEED, UNITS
from q3_revised_models import support

FOUNDATION=ROOT/'results/q3/round2/r2_20261127T155523Z/R2_1'
OUT=FOUNDATION.parent/'R2_2'
NBOOT=500
FIELDS=['any','H','V','A']+COMBOS
_DATA=None
_REFS=None
_SUPP=None


def outcomes(p):
    return np.column_stack([1-p[:,0]]+[p[:,[i for i,c in enumerate(COMBOS) if c[j]=='1']].sum(1) for j in range(3)]+[p[:,i] for i in range(8)])


def raw(d):
    c=d[d.Type=='call'];z=d[d.Type=='control'].set_index('expID')
    rows=[]
    for t in ['flat','mod','tv']:
        a=c[c.CallType==t];b=z.loc[a.expID]
        def observed(x):
            cc=combo(x)
            return np.column_stack([x.ResponseYesNo]+[x[k+'YesNo'] for k in ['HeadsUp','Vocal','Approach']]+[(cc==v).astype(int) for v in COMBOS])
        rows.append(np.stack([observed(a).mean(0),observed(b).mean(0)]))
    return np.stack(rows)


def adjusted(model,refs):
    vals=[]
    for t in ['flat','mod','tv']:
        r=refs[refs.call_type==t];x=r.rename(columns={'context':'Context'}).copy()
        a=x.copy();a['CallType']=t;b=x.copy();b['CallType']='control'
        vals.append(np.stack([np.average(outcomes(predict_combo(model,a)),axis=0,weights=r.weight),np.average(outcomes(predict_combo(model,b)),axis=0,weights=r.weight)]))
    return np.stack(vals)


def init(d,refs,supp):
    global _DATA,_REFS,_SUPP
    _DATA=d;_REFS=refs;_SUPP=supp


def worker(task):
    unit,rep=task
    result=dict(unit=unit,replicate=rep,success=False,missing_combos=[],warnings=[])
    with threadpool_limits(limits=1),warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        d,chosen=resample(_DATA,unit,rep)
        result['chosen_units']=chosen;result['raw']=raw(d)
        result['missing_combos']=sorted(set(COMBOS)-set(combo(d)))
        result['missing_types']=sorted(set(TYPES)-set(d.CallType))
        try:
            if result['missing_types']:raise ValueError('Absent stimulus type in bootstrap training sample')
            model=fit_combo(d,1);result['adjusted']=adjusted(model,_REFS)
            if len(_SUPP):result['supplement']=adjusted(model,_SUPP)
            assert np.isfinite(result['adjusted']).all()
            result['success']=True
        except Exception as exc:result['error']=str(exc)
        result['warnings']=[str(w.message) for w in caught]
    return result


def tabulate(point,reps,key,refs):
    rows=[]
    for unit in UNITS:
        selected=[r for r in reps if r['unit']==unit and key in r]
        a=np.stack([r[key] for r in selected])
        for j,t in enumerate(['flat','mod','tv']):
            for k,field in enumerate(FIELDS):
                delta=a[:,j,0,k]-a[:,j,1,k]
                delta=delta[np.isfinite(delta)]
                lo,hi=np.quantile(delta,[.025,.975])
                rows.append(dict(call_type=t,outcome=field,call_probability=point[j,0,k],control_probability=point[j,1,k],
                    probability_difference=point[j,0,k]-point[j,1,k],lower=lo,upper=hi,
                    reference_pair_n=int(refs[refs.call_type==t].exp_id.nunique()) if refs is not None else {'flat':48,'mod':33,'tv':58}[t],
                    resampling_unit=unit,bootstrap_success_n=len(delta),bootstrap_total_n=NBOOT,
                    missing_training_class_n=sum(bool(r['missing_combos']) for r in selected),
                    interval_method='pointwise_95pct_cluster_percentile_same_replicate_difference',
                    uncertainty_scope='fixed_C1_model_not_model_selection',
                    reference_scope='empirical_resampled_matched_pairs' if key=='raw' else 'conditional_on_fixed_supported_observed_reference',
                    inference_level='descriptive' if key=='raw' else 'model_adjusted_association'))
    return pd.DataFrame(rows)


def run():
    OUT.mkdir(parents=True,exist_ok=False)
    d=load_data();refs=pd.read_csv(FOUNDATION/'comparison_reference.csv').query("module=='pattern'")
    # The supplementary population requires support under all FOUR types; fixed before outcome comparisons.
    ids=[]
    for i,r in d.iterrows():
        if all(support(d[(d.CallType==t)&(d.Context==r.Context)][COLS[2:]].to_numpy(float),r[COLS[2:]].to_numpy(float)) in ['interpolation','boundary'] for t in TYPES):ids.append(i)
    supp=[]
    if ids:
        base=d.loc[ids]
        for t in ['flat','mod','tv']:
            for i,r in base.iterrows():
                x=dict(call_type=t,exp_id=r.expID,source_row_id=int(r._source_row_id),context=r.Context,weight=1/len(base))
                x.update({c:r[c] for c in COLS[2:]});supp.append(x)
    supp=pd.DataFrame(supp);supp.to_csv(OUT/'supplementary_reference.csv',index=False)
    model=fit_combo(d,1);point=adjusted(model,refs);rp=raw(d)
    sp=adjusted(model,supp) if len(supp) else None
    tasks=[(u,r) for u in UNITS for r in range(NBOOT)];results=[]
    with ProcessPoolExecutor(max_workers=4,initializer=init,initargs=(d,refs,supp)) as pool:
        for i,r in enumerate(pool.map(worker,tasks,chunksize=4)):
            results.append(r)
            if (i+1)%100==0:print('PATTERN BOOT',i+1,flush=True)
    tabulate(rp,results,'raw',None).to_csv(OUT/'pattern_observed_paired.csv',index=False)
    table=tabulate(point,results,'adjusted',refs);table.to_csv(OUT/'pattern_adjusted_contrasts.csv',index=False)
    if sp is not None:
        st=tabulate(sp,results,'supplement',supp);st['reference_scope']='fixed_empirical_rows_supported_under_all_four_types';st['reference_row_n']=len(ids)
        st['reference_pair_n']=np.nan;st.to_csv(OUT/'pattern_supplementary_standardization.csv',index=False)
    # Keep complete replicate predictions to support later H probability sharing.
    for u in UNITS:
        z=[r for r in results if r['unit']==u]
        np.savez_compressed(OUT/f'pattern_bootstrap_{u}.npz',adjusted=np.stack([r.get('adjusted',np.full((3,2,12),np.nan)) for r in z]),raw=np.stack([r['raw'] for r in z]))
    diagnostics=[{k:v for k,v in r.items() if k not in ['raw','adjusted','supplement']} for r in results]
    (OUT/'bootstrap_diagnostics.json').write_text(json.dumps(diagnostics,indent=2),encoding='utf-8')
    freq=[]
    pairs=pd.read_csv(FOUNDATION/'pair_mapping.csv')
    for t in ['flat','mod','tv']:
        pp=pairs[pairs.CallType_call==t]
        for side in ['call','control']:
            z=d[d._source_row_id.isin(pp['source_row_id_'+side])]
            for c in COMBOS:freq.append(dict(call_type=t,side=side,combo=c,n=int((combo(z)==c).sum()),total_n=len(z)))
    pd.DataFrame(freq).to_csv(OUT/'pattern_observed_frequencies.csv',index=False)
    # Reuse original GEE robust estimates and OOF rather than refit unchanged models.
    s2=ROOT/'results/q3/q3_stage2_20261127T115748Z'
    for f in ['gee_associations.csv','validation.csv']:(OUT/f).write_bytes((s2/f).read_bytes())
    figdir=ROOT/'figures/q3/round2'/FOUNDATION.parent.name;figdir.mkdir(parents=True,exist_ok=True)
    fig,ax=plt.subplots(figsize=(7,4));z=table.query("resampling_unit=='expID' and outcome in ['any','H','V','A']")
    for j,t in enumerate(['flat','mod','tv']):
        zz=z[z.call_type==t];xx=np.arange(4)+(j-1)*.18
        ax.errorbar(xx,zz.probability_difference*100,yerr=np.vstack([zz.probability_difference-zz.lower,zz.upper-zz.probability_difference])*100,fmt='o',label=t,capsize=3)
    ax.axhline(0,color='gray',lw=.8);ax.set_xticks(np.arange(4),['Any','Heads up','Vocal','Approach']);ax.set_ylabel('Adjusted probability difference (percentage points)');ax.legend();fig.tight_layout();fig.savefig(figdir/'pattern_matched_contrasts.png',dpi=180);plt.close(fig)
    assert np.allclose(point[:,:,4:].sum(2),1)
    assert np.allclose(point[:,:,0],1-point[:,:,4])
    meta=dict(stage='R2-2',foundation=str(FOUNDATION.relative_to(ROOT)),input_sha256=hashlib.sha256(INPUT.read_bytes()).hexdigest(),
        implementation_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),seed=SEED,bootstrap_per_unit=NBOOT,
        git_head=subprocess.check_output(['git','-c',f'safe.directory={ROOT.as_posix()}','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        versions=dict(python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__,scipy=scipy.__version__,sklearn=sklearn.__version__),
        supplementary_reference_rows=len(ids),model='fixed_C1_multinomial_original_HVA_278',
        acceptance=dict(joint_probabilities=True,same_replicate_contrasts=True,fixed_reference=True),
        success_by_unit={u:sum(r['success'] for r in results if r['unit']==u) for u in UNITS})
    (OUT/'metadata.json').write_text(json.dumps(meta,indent=2),encoding='utf-8');(OUT/'implementation_snapshot.py').write_bytes(Path(__file__).read_bytes())
    print(table.query("outcome=='any'").to_string(index=False),flush=True)


if __name__=='__main__':run()
