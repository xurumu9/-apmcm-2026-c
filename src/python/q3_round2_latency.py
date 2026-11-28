"""R2-4: separate response opportunity, zero atom and positive time."""
import json
import hashlib
import warnings
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from q3_playback_analysis import ROOT,INPUT,plt
from q3_uncertainty_delivery import load_data,resample,UNITS,SEED
from q3_count_latency_models import fit_time,predict_time,latency_population
from q3_round2_pattern import FOUNDATION,NBOOT

OUT=FOUNDATION.parent/'R2_4'
BEHAVIORS=['HeadsUp','Vocal','Approach']
FIELDS=['p_response','conditional_median_s','conditional_mean_s','positive_median_s','positive_mean_s','cdf_1s','cdf_5s','cdf_10s','cdf_30s','cdf_60s']
_DATA=None
_REF=None


def estimates(d,refs):
    result=np.full((3,3,2,len(FIELDS)),np.nan);diags=[]
    for j,b in enumerate(BEHAVIORS):
        pop=latency_population(d,b,'exclude_conflicts');diag=dict(behavior=b,success=False,train_n=len(pop),events=int(pop._event.sum()),positive_n=int(((pop._event==1)&(pop[b+'Latency']>0)).sum()))
        try:
            if set(['flat','mod','tv','control'])-set(pop.CallType):raise ValueError('Missing type')
            fit=fit_time(pop,b,'lognormal','type','window');diag.update(fit[2])
            if not fit[2]['success']:raise RuntimeError(fit[2]['message'])
            values=[]
            for t in ['flat','mod','tv']:
                r=refs[(refs.module=='latency_'+b)&(refs.call_type==t)];x=r.rename(columns={'context':'Context'}).copy()
                x['expID']=r.exp_id;x['_event']=0;x[b+'Latency']=np.nan
                sides=[]
                for stimulus in [t,'control']:
                    xx=x.copy();xx['CallType']=stimulus
                    pred=predict_time(pop,xx,b,'lognormal','type','window','exclude_conflicts',fit)
                    assert np.allclose(pred.mass_no_response+pred.mass_recorded_zero+pred.mass_positive,1)
                    assert np.allclose(pred.cdf_60s,pred.p_response)
                    sides.append(np.average(pred[FIELDS],weights=r.weight,axis=0))
                values.append(sides)
            result[j]=np.array(values);diag['success']=True
        except Exception as exc:diag['success']=False;diag['error']=str(exc)
        diags.append(diag)
    return result,diags


def init(d,refs):
    global _DATA,_REF
    _DATA=d;_REF=refs


def worker(task):
    u,k=task;row=dict(unit=u,replicate=k)
    with threadpool_limits(limits=1),warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always');d,chosen=resample(_DATA,u,k);row['sampled_units']=chosen
        row['estimate'],row['diagnostics']=estimates(d,_REF);row['warnings']=[str(x.message) for x in caught]
    return row


def decompose(d):
    oof=pd.read_csv(ROOT/'results/q3/q3_stage4_20261127T125945Z/latency_oof.csv');rows=[];cal=[]
    for key,g in oof.groupby(['route','behavior','version','model']):
        route,b,version,model=key
        common=latency_population(d,b,'exclude_conflicts')._source_row_id
        for scope,s in [('version_population',g),('common_evaluable',g[g.source_row_id.isin(common)])]:
            e=s.actual_event.to_numpy(bool);t=s.actual_latency_s.to_numpy();zero=e&(t==0);pos=e&(t>0);p=s.p_response.to_numpy();pi=s.pi_zero_given_response.to_numpy()
            gate=np.empty(len(s));gate[e]=-np.log(p[e]);gate[~e]=-np.log1p(-p[~e])
            atom=np.zeros(len(s));atom[zero]=-np.log(pi[zero]);atom[pos]=-np.log1p(-pi[pos])
            density=s.nll.to_numpy()-gate-atom
            assert np.allclose(density[~pos],0,atol=1e-8)
            rows.append(dict(route=route,behavior=b,version=version,model=model,scope=scope,n=len(s),event_n=int(e.sum()),zero_n=int(zero.sum()),positive_n=int(pos.sum()),
                gate_mean_nll=gate.mean(),atom_mean_nll=atom.mean(),density_mean_nll=density.mean(),joint_mean_nll=s.nll.mean(),
                responder_atom_nll=atom[e].mean() if e.any() else np.nan,positive_density_nll=density[pos].mean() if pos.any() else np.nan,
                conditional_median_mae=np.mean(abs(t[e]-s.conditional_median_s.to_numpy()[e])) if e.any() else np.nan))
            for cutoff in [1,5,10,30,60]:
                actual=(e&(t<=cutoff)).astype(int);pred=s[f'cdf_{cutoff}s'].to_numpy()
                cal.append(dict(route=route,behavior=b,version=version,model=model,scope=scope,cutoff_s=cutoff,bin='all',n=len(s),observed=actual.mean(),predicted=pred.mean(),brier=np.mean((actual-pred)**2)))
                for left in [0,.2,.4,.6,.8]:
                    keep=(pred>=left)&(pred<(left+.2) if left<.8 else pred<=1)
                    cal.append(dict(route=route,behavior=b,version=version,model=model,scope=scope,cutoff_s=cutoff,bin=f'{left:.1f}-{left+.2:.1f}',n=int(keep.sum()),observed=actual[keep].mean() if keep.any() else np.nan,predicted=pred[keep].mean() if keep.any() else np.nan,brier=np.mean((actual[keep]-pred[keep])**2) if keep.any() else np.nan))
    table=pd.DataFrame(rows);assert np.allclose(table.gate_mean_nll+table.atom_mean_nll+table.density_mean_nll,table.joint_mean_nll)
    table.to_csv(OUT/'latency_oof_score_decomposition.csv',index=False);pd.DataFrame(cal).to_csv(OUT/'latency_timepoint_calibration.csv',index=False)
    return table


def run():
    OUT.mkdir(parents=True,exist_ok=False);d=load_data();refs=pd.read_csv(FOUNDATION/'comparison_reference.csv');decompose(d)
    point,diags=estimates(d,refs);assert np.isfinite(point).all();results=[]
    with ProcessPoolExecutor(max_workers=4,initializer=init,initargs=(d,refs)) as pool:
        for i,r in enumerate(pool.map(worker,[(u,k) for u in UNITS for k in range(NBOOT)],chunksize=4)):
            results.append(r)
            if (i+1)%100==0:print('LATENCY BOOT',i+1,flush=True)
    rows=[]
    for u in UNITS:
        zz=[r for r in results if r['unit']==u];a=np.stack([r['estimate'] for r in zz]);np.savez_compressed(OUT/f'latency_bootstrap_{u}.npz',estimate=a)
        # Same resampling sequence and same H event/population: exact shared probability contrasts.
        pattern=np.load(FOUNDATION.parent/'R2_2'/f'pattern_bootstrap_{u}.npz')['adjusted']
        assert np.allclose(a[:,0,:,:,0],pattern[:,:,:,1],equal_nan=True)
        for j,b in enumerate(BEHAVIORS):
            for k,t in enumerate(['flat','mod','tv']):
                for m,f in enumerate(FIELDS):
                    delta=a[:,j,k,0,m]-a[:,j,k,1,m];good=np.isfinite(delta);lo,hi=np.quantile(delta[good],[.025,.975])
                    sub=refs[(refs.module=='latency_'+b)&(refs.call_type==t)]
                    rows.append(dict(behavior=b,call_type=t,estimand=f,call_estimate=point[j,k,0,m],control_estimate=point[j,k,1,m],difference=point[j,k,0,m]-point[j,k,1,m],lower=lo,upper=hi,
                        reference_pair_n=sub.exp_id.nunique(),resampling_unit=u,bootstrap_success_n=int(good.sum()),bootstrap_total_n=NBOOT,
                        bound_fit_n=sum(bool(r['diagnostics'][j].get('bound_hit')) for r in zz if r['diagnostics'][j]['success']),
                        reference_scope='fixed_supported_complete_paired_population',uncertainty_scope='fixed_model_conditional_on_reference_and_success_not_selection',
                        interval_method='pointwise95_cluster_percentile_same_replicate_difference',
                        inference_level='adjusted_window_association' if f=='p_response' else 'type_only_conditional_time_or_combined_cdf',
                        borrowed_control_positive_time=(b=='Approach'),shared_with_pattern=(b=='HeadsUp' and f=='p_response')))
    tab=pd.DataFrame(rows)
    tab[tab.estimand=='p_response'].to_csv(OUT/'latency_window_probability_contrasts.csv',index=False)
    tab[tab.estimand!='p_response'].to_csv(OUT/'latency_conditional_time_contrasts.csv',index=False)
    (OUT/'bootstrap_diagnostics.json').write_text(json.dumps([{k:v for k,v in r.items() if k!='estimate'} for r in results],indent=2),encoding='utf-8')
    meta=dict(stage='R2-4',input_sha256=hashlib.sha256(INPUT.read_bytes()).hexdigest(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),seed=SEED,bootstrap_per_unit=NBOOT,
        model='window_lognormal_type_exclude_conflicts',point_diagnostics=diags,inherited_environment='R2_2/metadata.json',
        acceptance=dict(mass_identity=True,cdf60_identity=True,score_decomposition=True,H_shared_replicates=True))
    (OUT/'metadata.json').write_text(json.dumps(meta,indent=2),encoding='utf-8');(OUT/'implementation_snapshot.py').write_bytes(Path(__file__).read_bytes())
    fig,ax=plt.subplots(figsize=(7,4));z=tab.query("resampling_unit=='expID' and estimand=='p_response'")
    for k,t in enumerate(['flat','mod','tv']):
        s=z[z.call_type==t];ax.errorbar(np.arange(3)+(k-1)*.18,s.difference*100,yerr=np.vstack([s.difference-s.lower,s.upper-s.difference])*100,fmt='o',label=t,capsize=3)
    ax.set_xticks(np.arange(3),['Heads up','Vocal','Approach']);ax.set_ylabel('Adjusted window probability difference (pp)');ax.axhline(0,color='gray',lw=.8);ax.legend();fig.tight_layout();fig.savefig(ROOT/'figures/q3/round2'/FOUNDATION.parent.name/'latency_window_contrasts.png',dpi=180);plt.close(fig)
    print(tab.query("resampling_unit=='expID' and estimand in ['p_response','conditional_median_s']").to_string(index=False),flush=True)


if __name__=='__main__':run()
