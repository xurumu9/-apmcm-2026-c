"""R2-3: count decomposition and fixed-model matched contrasts."""
import json
import hashlib
import warnings
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from q3_playback_analysis import ROOT,INPUT,COLS,plt
from q3_uncertainty_delivery import load_data,resample,UNITS,SEED
from q3_count_latency_models import fit_count,predict_count
from q3_round2_pattern import FOUNDATION,NBOOT

OUT=FOUNDATION.parent/'R2_3'
FIELDS=['q_positive','mean_positive','mean_total']
_DATA=None
_REF=None


def estimates(d,ref):
    fit=fit_count(d,'nb2','full')
    if not fit[2]['success']:raise RuntimeError(fit[2]['message'])
    rows=[]
    for t in ['flat','mod','tv']:
        r=ref[ref.call_type==t];x=r.rename(columns={'context':'Context'}).copy();x['VocalNcalls']=0;x['expID']=r.exp_id
        both=[]
        for stim in [t,'control']:
            xx=x.copy();xx['CallType']=stim;p=predict_count(d,xx,'nb2','full',fit)
            assert np.allclose(p.mean_total,p.q_positive*p.mean_positive)
            both.append(np.average(p[FIELDS],axis=0,weights=r.weight))
        rows.append(both)
    return np.array(rows),fit[2]


def init(d,ref):
    global _DATA,_REF
    _DATA=d;_REF=ref


def worker(task):
    u,k=task;result=dict(unit=u,replicate=k,success=False)
    with threadpool_limits(limits=1),warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        d,chosen=resample(_DATA,u,k);result['sampled_units']=chosen
        try:
            if set(['flat','mod','tv','control'])-set(d.CallType):raise ValueError('Missing type')
            result['estimate'],result['fit']=estimates(d,_REF);result['success']=True
        except Exception as exc:result['error']=str(exc)
        result['warnings']=[str(x.message) for x in caught]
    return result


def diagnostics(d):
    source=ROOT/'results/q3/q3_stage3_20261127T125020Z/count_oof.csv'
    oof=pd.read_csv(source);meta=d.set_index('_source_row_id')[['CallType','Context','Date','_natural_track']]
    z=oof.join(meta,on='source_row_id');rows=[];pieces=[]
    for (route,model),s in z.groupby(['route','model']):
        for axis in ['all','CallType','Context','Date','_natural_track']:
            groups=[('all',s)] if axis=='all' else s.groupby(axis)
            for label,g in groups:
                pos=g.actual>0
                row=dict(route=route,model=model,axis=axis,group=label,n=len(g),positive_n=int(pos.sum()),
                    observed_q=pos.mean(),predicted_q=g.q_positive.mean(),q_brier=np.mean((pos-g.q_positive)**2),
                    observed_positive_mean=g.loc[pos,'actual'].mean(),predicted_positive_mean=g.loc[pos,'mean_positive'].mean(),
                    observed_total_mean=g.actual.mean(),predicted_total_mean=g.mean_total.mean(),
                    positive_mean_residual=(g.loc[pos,'actual']-g.loc[pos,'mean_positive']).mean(),
                    total_mean_residual=(g.actual-g.mean_total).mean(),mean_nll=g.nll.mean())
                for k in [5,10]:row.update({f'observed_ge{k}':(g.actual>=k).mean(),f'predicted_ge{k}':g[f'prob_ge{k}'].mean(),f'event_ge{k}_n':int((g.actual>=k).sum())})
                rows.append(row)
        pos=s.actual>0
        # Exact observation-level decomposition of mean error. Not a causal attribution.
        gate_piece=s.mean_positive*(pos.astype(float)-s.q_positive)
        positive_piece=pos.astype(float)*(s.actual-s.mean_positive)
        assert np.allclose(gate_piece+positive_piece,s.actual-s.mean_total)
        pieces.append(dict(route=route,model=model,n=len(s),gate_weighted_error=gate_piece.mean(),
            positive_weighted_error=positive_piece.mean(),total_error=(s.actual-s.mean_total).mean(),
            interpretation='algebraic_OOF_error_decomposition_not_causal_or_unique'))
    pd.DataFrame(rows).to_csv(OUT/'count_calibration_and_tail.csv',index=False)
    pd.DataFrame(pieces).to_csv(OUT/'count_component_diagnostics.csv',index=False)
    base=z.query("route=='expID' and model=='hurdle_nb2_full'").copy()
    base['residual']=base.actual-base.mean_total
    influence=[]
    for axis in ['exp_id','_natural_track','Date']:
        for group,s in base.groupby(axis):
            rest=base.drop(s.index)
            influence.append(dict(axis=axis,group=group,n=len(s),actual_count_sum=s.actual.sum(),
                residual_sum=s.residual.sum(),remaining_oof_mean_residual=rest.residual.mean(),
                method='leave_cluster_from_existing_OOF_summary_not_refit_or_deletion'))
    pd.DataFrame(influence).to_csv(OUT/'count_cluster_contributions.csv',index=False)
    base[base.actual>=5].to_csv(OUT/'count_high_records_audit.csv',index=False)
    return pd.DataFrame(rows),pd.DataFrame(pieces)


def run():
    OUT.mkdir(parents=True,exist_ok=False);d=load_data();ref=pd.read_csv(FOUNDATION/'comparison_reference.csv').query("module=='count'")
    cal,pieces=diagnostics(d);point,diag=estimates(d,ref);results=[]
    with ProcessPoolExecutor(max_workers=4,initializer=init,initargs=(d,ref)) as pool:
        for i,r in enumerate(pool.map(worker,[(u,k) for u in UNITS for k in range(NBOOT)],chunksize=4)):
            results.append(r)
            if (i+1)%100==0:print('COUNT BOOT',i+1,flush=True)
    rows=[]
    for u in UNITS:
        reps=[r for r in results if r['unit']==u];good=[r for r in reps if r['success']]
        a=np.stack([r['estimate'] for r in good]);np.savez_compressed(OUT/f'count_bootstrap_{u}.npz',replicate=[r['replicate'] for r in good],estimate=a)
        for j,t in enumerate(['flat','mod','tv']):
            for k,f in enumerate(FIELDS):
                delta=a[:,j,0,k]-a[:,j,1,k];lo,hi=np.quantile(delta,[.025,.975])
                rows.append(dict(call_type=t,estimand=f,call_estimate=point[j,0,k],control_estimate=point[j,1,k],difference=point[j,0,k]-point[j,1,k],
                    lower=lo,upper=hi,reference_pair_n=int(ref[ref.call_type==t].exp_id.nunique()),resampling_unit=u,
                    bootstrap_success_n=len(good),bootstrap_total_n=NBOOT,bound_fit_n=sum(bool(r['fit']['bound_hit']) for r in good),
                    reference_scope='fixed_supported_matched_pairs',uncertainty_scope='fixed_NB2_penalty1_conditional_on_reference_and_success_not_selection',
                    interval_method='pointwise95_cluster_percentile_same_replicate_difference',
                    unit='probability' if f=='q_positive' else 'calls_per_group_playback',
                    interpretation='different_positive_responder_composition' if f=='mean_positive' else 'model_adjusted_association'))
    tab=pd.DataFrame(rows);tab.to_csv(OUT/'count_paired_contrasts.csv',index=False)
    diagall=[{k:v for k,v in r.items() if k!='estimate'} for r in results]
    (OUT/'count_bootstrap_diagnostics.json').write_text(json.dumps(diagall,indent=2),encoding='utf-8')
    (OUT/'duration_identifiability.md').write_text('# 持续时间\n\nR2-1未获得60编码、结束标记/上限及逐条观察界限的新证据。沿用第一轮S5审计；不能识别真实行为持续时间，也不能给声音类型的真实时长排名或正式区间。记录工作模型不替代真实时长模型。\n',encoding='utf-8')
    meta=dict(stage='R2-3',input_sha256=hashlib.sha256(INPUT.read_bytes()).hexdigest(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        foundation=str(FOUNDATION.relative_to(ROOT)),seed=SEED,bootstrap_per_unit=NBOOT,model='hurdle_NB2_full_penalty1',point_diagnostics=diag,
        inherited_environment='R2_2/metadata.json',model_n=278,positive_n=85,formal_duration_ready=False,
        acceptance=dict(mean_product_identity=True,error_decomposition_identity=True,matched_reference=True))
    (OUT/'metadata.json').write_text(json.dumps(meta,indent=2),encoding='utf-8');(OUT/'implementation_snapshot.py').write_bytes(Path(__file__).read_bytes())
    figdir=ROOT/'figures/q3/round2'/FOUNDATION.parent.name
    fig,ax=plt.subplots(figsize=(6,3.5));z=tab.query("resampling_unit=='expID' and estimand=='mean_total'")
    ax.errorbar(np.arange(3),z.difference,yerr=np.vstack([z.difference-z.lower,z.upper-z.difference]),fmt='o',capsize=4)
    ax.set_xticks(np.arange(3),['Flat','Mod','TV']);ax.set_ylabel('Adjusted difference in expected calls');ax.axhline(0,color='gray',lw=.8);fig.tight_layout();fig.savefig(figdir/'intensity_matched_contrasts.png',dpi=180);plt.close(fig)
    print(tab.to_string(index=False),flush=True);print(cal.query("axis=='all'").to_string(index=False),flush=True)


if __name__=='__main__':run()
