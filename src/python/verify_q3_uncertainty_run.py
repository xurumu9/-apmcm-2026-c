"""Read saved stage-6 draws and independently verify delivery arithmetic and provenance."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import nbinom
from q3_uncertainty_delivery import (ROOT,INPUT,SEED,UNITS,COUNT_FIELDS,TIME_FIELDS,BEHAVIORS,
    load_data,grid_from,interval,sha)


def same_ci(row,values,total):
    finite=values[np.isfinite(values)]
    lo,hi=np.quantile(finite,[.025,.975]) if len(finite) else [np.nan,np.nan]
    np.testing.assert_allclose([row.lower,row.upper],[lo,hi],equal_nan=True,atol=1e-10)
    assert row.bootstrap_success_n==len(finite) and row.bootstrap_total_n==total
    if len(finite)<total:assert 'conditional_on_successful' in row.interval_scope


def verify(out):
    meta=json.loads((out/'metadata.json').read_text());b=meta['replicates_per_unit'];m=meta['predictive_draws_per_replicate']
    assert meta['full_analysis'] and b>=500 and meta['uncertainty_scope']=='fixed_models_and_analysis_rules_not_model_selection'
    assert sha(INPUT)==meta['input_sha256'] and sha(out/'implementation_snapshot.py')==meta['script_sha256']
    for name,value in meta['helper_sha256'].items():assert sha(ROOT/'src/python'/name)==value
    d=load_data();g,s=grid_from(ROOT/meta['stage1_run']);keys={(r.CallType,r.Context,r.Distance):i for i,r in g.iterrows()}
    c=pd.read_csv(out/'combination_predictions.csv',dtype={'combo':str})
    t=pd.read_csv(out/'latency_intensity_predictions.csv');p=pd.read_csv(out/'future_experiment_prediction_intervals.csv')
    contrasts=pd.read_csv(out/'representative_call_control_contrasts.csv',dtype={'combo':str})
    sets=pd.read_csv(out/'combination_future_prediction_sets.csv',dtype={'prediction_set':str})
    parameters=pd.read_csv(out/'parameter_confidence_intervals.csv')
    diags=json.loads((out/'bootstrap_diagnostics.json').read_text());trace=json.loads((out/'resampling_manifest.json').read_text())
    assert len(trace)==2*b and len(diags)==10*b
    assert len(c)==576 and len(t)==3384 and len(p)==288 and len(sets)==72 and len(contrasts)==432
    assert not c.duplicated(['resampling_unit','call_type','context','distance_m','combo']).any()
    assert np.allclose(c.groupby(['resampling_unit','call_type','context','distance_m']).probability.sum(),1)
    assert np.isfinite(c[['probability','lower','upper']]).all().all()
    stage3=pd.read_csv(ROOT/'results/q3/q3_stage3_20261127T125020Z/count_predictions.csv')
    stage4=pd.read_csv(ROOT/'results/q3/q3_stage4_20261127T125945Z/latency_predictions.csv')
    stage2=pd.read_csv(ROOT/'results/q3/q3_stage2_20261127T115748Z/combination_predictions.csv',dtype={'combo':str})
    for r in trace:
        unit=r['unit'];key='expID' if unit=='expID' else '_natural_track';labels=d[key].drop_duplicates().to_numpy()
        rng=np.random.default_rng(np.random.SeedSequence([SEED,UNITS.index(unit),r['replicate'],0]))
        chosen=rng.choice(labels,len(labels),replace=True).tolist();assert chosen==r['sampled_units']
        sizes=d.groupby(key).size();pairs=d.groupby(key).expID.nunique()
        assert r['sampled_rows_n']==sum(int(sizes[x]) for x in chosen)
        assert r['new_pair_n']==sum(int(pairs[x]) for x in chosen)
    for unit in UNITS:
        z=np.load(out/f'bootstrap_{unit}.npz')
        bc,bn,bt=z['combo'],z['count'],z['time'];cd,td,tk=z['count_draws'],z['time_draws'],z['time_kind']
        assert bc.shape==(b,36,8) and bn.shape==(b,36,4) and bt.shape==(b,3,36,14)
        assert cd.shape==(b,m,36) and td.shape==(b,3,m,36) and tk.shape==td.shape
        np.testing.assert_allclose(bc.sum(2)[np.isfinite(bc).all(2)],1,atol=1e-10)
        np.testing.assert_allclose(bn[:,:,2],bn[:,:,0]*bn[:,:,1],equal_nan=True)
        # Recover NB2 base mu from the saved truncated mean, independently of ppf.
        alpha=z['parameters'][:,0,None];mean=bn[:,:,1];q=bn[:,:,0];median=bn[:,:,3]
        lo=np.zeros_like(mean);hi=mean.copy()
        for _ in range(60):
            mu=(lo+hi)/2;nz=-np.expm1(-np.log1p(alpha*mu)/alpha);smaller=mu/nz<mean
            lo=np.where(smaller,mu,lo);hi=np.where(smaller,hi,mu)
        mu=(lo+hi)/2;size=1/alpha;prob=1/(1+alpha*mu);p0=nbinom.pmf(0,size,prob)
        fm=1-q+q*(nbinom.cdf(median,size,prob)-p0)/(1-p0);fm=np.where(median==0,1-q,fm)
        previous=1-q+q*(nbinom.cdf(median-1,size,prob)-p0)/(1-p0);previous=np.where(median==0,0,previous)
        good=np.isfinite(median)
        assert (fm[good]>=.5-1e-10).all() and (previous[good]<=.5+1e-10).all()
        idx={field:i for i,field in enumerate(TIME_FIELDS)}
        masses=bt[:,:,:,idx['mass_no_response']]+bt[:,:,:,idx['mass_recorded_zero']]+bt[:,:,:,idx['mass_positive']]
        np.testing.assert_allclose(masses[np.isfinite(masses)],1,atol=1e-10)
        np.testing.assert_allclose(bt[:,:,:,idx['p_response']],bt[:,:,:,idx['cdf_60s']],equal_nan=True)
        h=bt[:,0,:,idx['p_response']];hc=bc[:,:,[4,5,6,7]].sum(2);both=np.isfinite(h)&np.isfinite(hc)
        np.testing.assert_allclose(h[both],hc[both],atol=1e-10)
        cdf=bt[:,:,:,[idx[f'cdf_{q}s'] for q in [1,5,10,30,60]]]
        assert (np.diff(cdf,axis=3)[np.isfinite(np.diff(cdf,axis=3))]>=-1e-10).all()
        assert np.isnan(td[tk<=0]).all() and (td[tk==1]==0).all()
        assert ((td[tk==2]>=0)&(td[tk==2]<=60+1e-10)).all()
        finite=cd[np.isfinite(cd)];assert (finite>=0).all() and np.all(finite==np.floor(finite))
        for component,arr in [('combo',bc),('count',bn)]+[(name,bt[:,j]) for j,name in enumerate(BEHAVIORS)]:
            ds=sorted([r for r in diags if r['unit']==unit and r['component']==component],key=lambda r:r['replicate'])
            assert len(ds)==b and np.array_equal(np.isfinite(arr).reshape(b,-1).all(1),[r['success'] for r in ds])
        for row in c[c.resampling_unit==unit].itertuples():
            k=keys[(row.call_type,row.context,row.distance_m)];j=int(row.combo,2);same_ci(row,bc[:,k,j],b)
            previous=stage2[(stage2.call_type==row.call_type)&(stage2.context==row.context)&(stage2.distance_m==row.distance_m)&(stage2.combo==row.combo)].iloc[0]
            np.testing.assert_allclose(row.probability,previous.probability,atol=1e-10)
        for row in t[t.resampling_unit==unit].itertuples():
            k=keys[(row.call_type,row.context,row.distance_m)]
            if row.outcome=='VocalNcalls':
                j=COUNT_FIELDS.index(row.estimand);values=bn[:,k,j]
                old=stage3[(stage3.model=='hurdle_nb2_full')&(stage3.call_type==row.call_type)&(stage3.context==row.context)&(stage3.distance_m==row.distance_m)].iloc[0]
            else:
                j=BEHAVIORS.index(row.behavior);q=TIME_FIELDS.index(row.estimand);values=bt[:,j,k,q]
                old=stage4[(stage4.behavior==row.behavior)&(stage4.model=='window_lognormal_type')&(stage4.version=='exclude_conflicts')&(stage4.call_type==row.call_type)&(stage4.context==row.context)&(stage4.distance_m==row.distance_m)].iloc[0]
            same_ci(row,values,b);np.testing.assert_allclose(row.estimate,old[row.estimand],atol=1e-8)
        for row in contrasts[contrasts.resampling_unit==unit].itertuples():
            k=keys[(row.call_type,row.context,row.distance_m)];control=keys[('control',row.context,row.distance_m)]
            same_ci(row,bc[:,k,int(row.combo,2)]-bc[:,control,int(row.combo,2)],b)
        for j,row in enumerate(parameters[parameters.resampling_unit==unit].itertuples()):same_ci(row,z['parameters'][:,j],b)
        for row in p[p.resampling_unit==unit].itertuples():
            k=keys[(row.call_type,row.context,row.distance_m)]
            if row.outcome=='VocalNcalls':
                values=cd[:,:,k];values=values[np.isfinite(values)];expected=np.quantile(values,[.025,.975],method='inverted_cdf')
                assert row.predictive_valid_n==len(values)
            else:
                j=BEHAVIORS.index(row.behavior);values=td[:,j,:,k][tk[:,j,:,k]>0]
                expected=np.quantile(values,[.025,.975]) if len(values) else [np.nan,np.nan]
                assert row.predictive_response_draws_n==len(values)
            np.testing.assert_allclose([row.prediction_lower,row.prediction_upper],expected,equal_nan=True,atol=1e-10)
        for row in sets[sets.resampling_unit==unit].itertuples():
            k=keys[(row.call_type,row.context,row.distance_m)];mix=np.nanmean(bc[:,k,:],axis=0)
            selected=[int(x,2) for x in row.prediction_set.split('|')]
            assert len(selected)==row.set_size and mix[selected].sum()>=.95-1e-10
            if len(selected)>1:assert mix[selected[:-1]].sum()<.95+1e-10
    duration=t[t.resampling_unit=='not_applicable'];assert len(duration)==72
    assert duration[['estimate','lower','upper']].isna().all().all()
    assert (duration.availability=='not_identified_duration_encoding_unresolved').all()
    old_duration=json.loads((ROOT/meta['stage5_run']/'metadata.json').read_text())
    assert sha(ROOT/'src/python/q3_duration_diagnostics.py')==old_duration['script_sha256']
    for _,row in pd.read_csv(ROOT/'file_manifest.csv').iterrows():assert sha(ROOT/row.Destination).lower()==row.SHA256.lower()
    acceptance=dict(accepted=True,replicates_per_unit=b,predictive_draws_per_replicate=m,
        checks=['input/provenance and raw38','cluster seeds and duplicate pair identities','probability and event interfaces',
                'conditional mean identities and count median inverse CDF','saved-draw percentile CI reconstruction','prior point predictions unchanged',
                'future predictive quantiles and no-response NaN','categorical prediction sets','duration unavailable interface'],
        note='Software/numerical acceptance only; no external coverage or biological identifiability certification.')
    (out/'acceptance.json').write_text(json.dumps(acceptance,indent=2),encoding='utf-8')
    print(json.dumps(acceptance,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('run',type=Path);a=p.parse_args()
    verify(a.run if a.run.is_absolute() else ROOT/a.run)
