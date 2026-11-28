"""Approved Q3 final semantic revision. Independent outputs; fixed models only.

Stages 1/2 audit and recombine existing draws, stage 3 diagnoses existing fixed
models (two necessary C1 fits for unsaved point gates), stage 4 exports evidence.
No probability calibration, family search, raw recoding, or historical writes.
"""
import argparse
import hashlib
import json
import platform
import subprocess
from datetime import datetime,timezone
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
import sklearn
from scipy.stats import nbinom
from threadpoolctl import threadpool_limits
from q3_playback_analysis import ROOT,INPUT,COLS,COMBOS,TYPES,fit_combo,predict_combo,plt
from q3_count_latency_models import (matrix_fit,matrix_apply,latency_population,
    binary_gate,time_logs,time_quantile,TIME_PENALTY)
from q3_revised_models import support
from q3_uncertainty_delivery import load_data,resample,grid_from,TIME_FIELDS,UNITS,SEED

S1=ROOT/'results/q3/q3_stage1_20261127T115630Z'
S2=ROOT/'results/q3/q3_stage2_20261127T115748Z'
S3=ROOT/'results/q3/q3_stage3_20261127T125020Z'
S4=ROOT/'results/q3/q3_stage4_20261127T125945Z'
S6=ROOT/'results/q3/q3_stage6_full_20261127T133654Z'
R2=ROOT/'results/q3/round2/r2_20261127T155523Z'
B=['HeadsUp','Vocal','Approach']
EPS=1e-8
SEMANTICS='P(final_original_VocalYesNo=1_and_recorded_VocalLatency<=t);not_first_baseline_crossing_time'


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def readj(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def writej(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def saveframe(p,x):pd.DataFrame(x).to_csv(p,index=False)
def marginals(p):
    return np.stack([p[..., [i for i,c in enumerate(COMBOS) if c[j]=='1']].sum(-1) for j in range(3)],axis=-1)
def type_design(types):
    return np.column_stack([np.ones(len(types))]+[(np.asarray(types)==t).astype(float) for t in TYPES[1:]])
def event_id(b):return 'original_'+b+'YesNo'+('_equals_post_gt_pre_in_this_file' if b=='Vocal' else '')
def time_semantics(b):return SEMANTICS if b=='Vocal' else 'P(original_'+b+'YesNo=1_and_recorded_latency<=t)'


def snapshot(out,stage,extra=None):
    commit=subprocess.check_output(['git','-c',f'safe.directory={ROOT.as_posix()}','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    info=dict(stage=stage,input_sha256=sha(INPUT),script_sha256=sha(__file__),seed=SEED,
        git_head=commit,working_tree='uncommitted',versions=dict(python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__,scipy=scipy.__version__,sklearn=sklearn.__version__),
        reference_scope='fixed_supported_type_specific_matched_pairs',probability_calibration=False,model_search=False)
    info.update(extra or {});writej(out/f'stage{stage}_metadata.json',info)
    (out/f'stage{stage}_implementation_snapshot.py').write_bytes(Path(__file__).read_bytes())


def stage1(out):
    out.mkdir(parents=True,exist_ok=False)
    # Historical manifests are taken before any new product is written.
    protected={}
    for folder in ['data','results','figures','src','experiments','paper','problem']:
        for p in (ROOT/folder).rglob('*'):
            if p.is_file() and out not in p.parents and p.resolve()!=Path(__file__).resolve():protected[str(p.relative_to(ROOT))]=sha(p)
    writej(out/'historical_hashes.json',protected)
    d=load_data();assert len(d)==278 and d.VocalYesNo.eq(d.VocalNcalls.gt(d.VocalNcallsBefore)).all()
    assert d.VocalRelNCalls.eq((d.VocalNcalls-d.VocalNcallsBefore).clip(lower=0)).all()
    refs=pd.read_csv(R2/'R2_1/comparison_reference.csv').query("module=='pattern'")
    pairs=pd.read_csv(R2/'R2_1/pair_mapping.csv');assert len(pairs)==139 and pairs.expID.is_unique
    assert refs.groupby('call_type').exp_id.nunique().to_dict()==dict(flat=30,mod=20,tv=39)
    assert refs.groupby(['call_type','exp_id']).size().eq(2).all() and np.allclose(refs.groupby('call_type').weight.sum(),1)
    refs.to_csv(out/'final_matched_reference.csv',index=False)
    rows=[]
    for b in B:
        rows.append(dict(module='Pattern_and_Latency',behavior=b,event_definition=event_id(b),model_n=278,event_n=int(d[b+'YesNo'].sum()),
            complete_pair_n=139,call_type_specific_supported_pairs='flat30_mod20_tv39',primary=True,unit='probability_or_seconds',
            time_population='original_flag_one_only',semantics=time_semantics(b)))
        p=latency_population(d,b,'exclude_conflicts');rows.append(dict(module='Latency_old_filtered_sensitivity',behavior=b,event_definition=event_id(b),model_n=len(p),event_n=int(p._event.sum()),primary=False,unit='probability_or_seconds'))
    rows.append(dict(module='Count',behavior='Vocal',event_definition='N_after>0',model_n=278,event_n=int((d.VocalNcalls>0).sum()),primary=True,unit='calls_per_group_playback',semantics='distinct_from_VocalYesNo'))
    rows.append(dict(module='Duration',behavior='HeadsUp_and_Approach',model_n=np.nan,event_n=np.nan,primary=False,unit='seconds',semantics='not_identified_no_formal_numeric_input'))
    saveframe(out/'final_estimands_and_populations.csv',rows)
    # Original OOF gate vs the exact C1 marginal on the same fold and row.
    combo=pd.read_csv(S2/'oof_combinations.csv',dtype={'actual_combo':str}).query("route=='expID' and model=='fixed_C1'").set_index('source_row_id')
    latency=pd.read_csv(S4/'latency_oof.csv');folds=readj(S1/'metadata.json')['reused_outer_folds']
    foldmap={i:f['fold'] for f in folds for i in f['test_rows']};gate=[]
    for j,b in enumerate(B):
        ver='exclude_conflicts' if b=='HeadsUp' else 'original_flags'
        z=latency[(latency.route=='expID')&(latency.behavior==b)&(latency.version==ver)&(latency.model=='window_lognormal_type')].sort_values('source_row_id')
        assert len(z)==278 and z.source_row_id.nunique()==278
        p=combo.loc[z.source_row_id,['p_'+c for c in COMBOS]].to_numpy();m=marginals(p)[:,j]
        assert np.allclose(m,z.p_response,atol=1e-12,rtol=0) and (z.fold.to_numpy()==z.source_row_id.map(foldmap).to_numpy()).all()
        for k,(_,r) in enumerate(z.iterrows()):gate.append(dict(behavior=b,source_row_id=int(r.source_row_id),fold=int(r.fold),pattern_probability=m[k],latency_probability=r.p_response,absolute_difference=abs(m[k]-r.p_response)))
    saveframe(out/'oof_gate_consistency.csv',gate)
    # Check full-fit and original-fold positive-time parameter equality, no fit.
    diags=readj(S4/'fit_diagnostics.json');paramchecks=[]
    for b in B[1:]:
        for a in [x for x in diags if x['behavior']==b and x['version']=='original_flags' and x['model']=='window_lognormal_type']:
            z=[x for x in diags if x['behavior']==b and x['version']=='exclude_conflicts' and x['model']=='window_lognormal_type' and x['route']==a['route'] and x['fold']==a['fold']]
            assert len(z)==1;delta=float(np.max(abs(np.array(a['params'])-z[0]['params'])));assert delta<1e-8
            paramchecks.append(dict(behavior=b,route=a['route'],fold=a['fold'],maximum_parameter_difference=delta))
    saveframe(out/'existing_time_parameter_equivalence.csv',paramchecks)
    s6manifest={(x['unit'],x['replicate']):x for x in readj(S6/'resampling_manifest.json')}
    r2pattern={(x['unit'],x['replicate']):x for x in readj(R2/'R2_2/bootstrap_diagnostics.json')}
    r2time={(x['unit'],x['replicate']):x for x in readj(R2/'R2_4/bootstrap_diagnostics.json')}
    checks=[];matrices={}
    # Type-only matrices are known category indicators; preprocessing fitted on
    # excluded negatives cannot alter these fixed CallType columns.
    for u in UNITS:
        with np.load(S6/f'bootstrap_{u}.npz') as arc:s6={key:arc[key] for key in ['parameters','time']}
        paired=np.load(R2/'R2_2'/f'pattern_bootstrap_{u}.npz')['adjusted']
        for k in range(500):
            train,chosen=resample(d,u,k)
            assert chosen==s6manifest[u,k]['sampled_units']==r2pattern[u,k]['chosen_units']==r2time[u,k]['sampled_units']
            for j,b in enumerate(B):
                allpop=latency_population(train,b,'original_flags');filtered=latency_population(train,b,'exclude_conflicts')
                positive=(allpop._event==1)&(allpop[b+'Latency']>0);fp=(filtered._event==1)&(filtered[b+'Latency']>0)
                a=allpop.loc[positive];f=filtered.loc[fp]
                assert a.index.equals(f.index) and np.array_equal(a[b+'Latency'].to_numpy(),f[b+'Latency'].to_numpy())
                assert np.array_equal(type_design(a.CallType),type_design(f.CallType))
                assert int(allpop._event.sum())==int(filtered._event.sum())
                assert int(((allpop._event==1)&(allpop[b+'Latency']==0)).sum())==int(((filtered._event==1)&(filtered[b+'Latency']==0)).sum())
                diag=r2time[u,k]['diagnostics'][j];assert diag['success']
                pars=np.array(diag['params']);assert abs(np.exp(pars[-1])-s6['parameters'][k,j+1])<1e-7
                pi=diag['zero_n']/diag['event_n'];x=type_design(TYPES);eta=x@pars[:-1]
                median=np.zeros(4);uq=(.5-pi)/(1-pi)
                if uq>0:median=time_quantile(np.full(4,uq),eta,pars[-1],'lognormal')
                grid,_=grid_from(S1)
                expected=median[[TYPES.index(t) for t in grid.CallType]]
                err=float(np.max(abs(expected-s6['time'][k,j,:,TIME_FIELDS.index('conditional_median_s')])));assert err<1e-7
                checks.append(dict(unit=u,replicate=k,behavior=b,sampling_aligned=True,positive_rows_and_type_matrix_equal=True,
                    same_window_objective_initialisation_penalty_bounds=True,zero_mass_equal=True,maximum_median_reconstruction_error=err,
                    success=diag['success'],bound_hit=bool(diag['bound_hit'])))
        # Paired H uses the same draw and marginal, checked against S6 only by matching sampling;
        # grid and observed references differ and are never interchanged.
        assert paired.shape==(500,3,2,12)
    saveframe(out/'bootstrap_reuse_equivalence.csv',checks)
    sources=[S2/'oof_combinations.csv',S4/'latency_oof.csv',S4/'fit_diagnostics.json',R2/'R2_2/pattern_adjusted_contrasts.csv',R2/'R2_3/count_paired_contrasts.csv']
    sources += [S6/f'bootstrap_{u}.npz' for u in UNITS]+[R2/'R2_4/bootstrap_diagnostics.json']
    saveframe(out/'reuse_and_recalculation_manifest.csv',[dict(path=str(p.relative_to(ROOT)),sha256=sha(p),use='reuse_with_event_reference_draw_identity_checks') for p in sources])
    snapshot(out,1,dict(fits_performed=0,accepted=True,original_oof_rows=834,bootstrap_component_equivalence_checks=len(checks),gate_max_abs_difference=max(x['absolute_difference'] for x in gate)))
    print('STAGE1 PASS',out,'OOF 834; bootstrap component checks',len(checks),flush=True)


def grid_points():
    grid,supports=grid_from(S1);meta=supports[supports.analysis_population_id=='combo_all_v1'].reset_index(drop=True)
    c=pd.read_csv(S6/'combination_predictions.csv').query("resampling_unit=='expID'")
    p=[]
    for _,r in meta.iterrows():
        z=c[(c.call_type==r.call_type)&(c.context==r.context)&(c.distance_m==r.distance_m)].set_index('combo')
        # read_csv can parse 000 as an integer without an explicit dtype.
        z.index=z.index.astype(str).str.zfill(3);p.append(z.loc[COMBOS,'probability'].to_numpy())
    return grid,meta,np.stack(p)


def mix_time(old,p):
    result=old.copy();idx={f:i for i,f in enumerate(TIME_FIELDS)}
    previous=old[...,idx['p_response']];assert (previous>0).all()
    pi=old[...,idx['pi_zero_given_response']]
    result[...,idx['p_response']]=p;result[...,idx['mass_no_response']]=1-p
    result[...,idx['mass_recorded_zero']]=p*pi;result[...,idx['mass_positive']]=p*(1-pi)
    for t in [1,5,10,30,60]:result[...,idx[f'cdf_{t}s']]=p*old[...,idx[f'cdf_{t}s']]/previous
    assert np.allclose(result[...,idx['cdf_60s']],p,atol=1e-10)
    assert np.allclose(result[...,idx['mass_no_response']]+result[...,idx['mass_recorded_zero']]+result[...,idx['mass_positive']],1)
    return result


def evidence(d,grid,meta):
    rows=[]
    for j,b in enumerate(B):
        for k,g in grid.iterrows():
            typ=d[(d.CallType==g.CallType)&(d[b+'YesNo']==1)&(d[b+'Latency']>0)]
            cell=typ[typ.Context==g.Context];source='positive_in_type_context'
            if not len(typ):source='no_positive_time_in_type_model_borrows_other_types'
            elif not len(cell):source='positive_in_type_only_no_context_direct_time'
            row=meta.iloc[k].to_dict();row.update(grid_row=k,behavior=b,model_population_n=278,event_definition=event_id(b),
                positive_time_type_n=len(typ),positive_time_context_type_n=len(cell),positive_time_evidence=source,
                conditional_time_joint_support=support(cell[COLS[2:]].to_numpy(float),g[COLS[2:]].to_numpy(float)),
                time_adjustment='type_only',cdf_semantics=time_semantics(b),
                availability='model_borrowed_conditional_time_sensitivity_only' if not len(typ) else 'exploratory_fixed_model_keep_support_limits')
            rows.append(row)
    return pd.DataFrame(rows)


def oof_summary(s,scope):
    e=s.actual_event.to_numpy(bool);t=s.actual_latency_s.to_numpy();p=s.p_response.to_numpy();pi=s.pi_zero_given_response.to_numpy()
    gate=np.where(e,-np.log(p),-np.log1p(-p));zero=e&(t==0);pos=e&(t>0);atom=np.zeros(len(s))
    atom[zero]=-np.log(pi[zero]);atom[pos]=-np.log1p(-pi[pos]);density=s.nll.to_numpy()-gate-atom
    assert np.allclose(density[~pos],0,atol=1e-8)
    result=dict(n=len(s),event_n=int(e.sum()),zero_n=int(zero.sum()),positive_n=int(pos.sum()),scope=scope,
        mean_joint_nll=s.nll.mean(),gate_mean_nll=gate.mean(),atom_mean_nll=atom.mean(),density_mean_nll=density.mean(),
        response_brier=np.mean((e-p)**2),conditional_median_mae=np.mean(abs(t[e]-s.conditional_median_s.to_numpy()[e])),
        predicted_response=p.mean(),observed_response=e.mean())
    for cutoff in [1,5,10,30,60]:result[f'brier_{cutoff}s']=np.mean(((e&(t<=cutoff))-s[f'cdf_{cutoff}s'])**2)
    return result


def revise_oof(out,d):
    old=pd.read_csv(S4/'latency_oof.csv');folds=readj(S1/'metadata.json')['reused_outer_folds'];scores=[];all_oof=[];cal=[]
    for b in B:
        version='exclude_conflicts' if b=='HeadsUp' else 'original_flags'
        main=old[(old.route=='expID')&(old.behavior==b)&(old.version==version)&(old.model=='window_lognormal_type')].copy()
        assert len(main)==278
        baseparts=[]
        for f in folds:
            train=d.iloc[np.array(f['train_rows'])-1];test=d.iloc[np.array(f['test_rows'])-1]
            source=old[(old.route=='expID')&(old.behavior==b)&(old.version=='exclude_conflicts')&(old.model=='window_lognormal_intercept')&(old.fold==f['fold'])]
            row=source.iloc[0];part=main[main.fold==f['fold']].copy();part=part.set_index('source_row_id').loc[test._source_row_id].reset_index()
            ev=test[b+'YesNo'].to_numpy(bool);time=test[b+'Latency'].to_numpy();q=float(train[b+'YesNo'].mean())
            pi=float(((train[b+'YesNo']==1)&(train[b+'Latency']==0)).sum()/train[b+'YesNo'].sum())
            nll=np.where(ev,-np.log(q),-np.log1p(-q));zero=ev&(time==0);pos=ev&(time>0)
            if zero.any():nll[zero]-=np.log(pi)
            nll[pos]-=np.log1p(-pi)
            source=source.set_index('source_row_id')
            for i,sourceid in enumerate(test._source_row_id):
                if pos[i]:
                    s=source.loc[sourceid]
                    density=s.nll+np.log(s.p_response)+np.log1p(-s.pi_zero_given_response)
                    nll[i]+=density
            for field in ['conditional_median_s','conditional_mean_s','positive_median_s','positive_mean_s']:part[field]=row[field]
            part['p_response']=q;part['pi_zero_given_response']=pi;part['mass_no_response']=1-q
            part['mass_recorded_zero']=q*pi;part['mass_positive']=q*(1-pi);part['nll']=nll
            for t in [1,5,10,30,60]:part[f'cdf_{t}s']=q*row[f'cdf_{t}s']/row.p_response
            part['model']='reassembled_original_intercept_reference';part['version']='original_flags';baseparts.append(part)
        base=pd.concat(baseparts,ignore_index=True)
        for label,s in [('final_original_flags',main),('reassembled_intercept_reference',base)]:
            s=s.copy();s['final_role']=label;s['cdf_semantics']=time_semantics(b);all_oof.append(s)
            for scope,z in [('all278',s),('common_evaluable_with_old_filter',s[s.source_row_id.isin(latency_population(d,b,'exclude_conflicts')._source_row_id)])]:
                scores.append(dict(behavior=b,version=label,route='expID',**oof_summary(z,scope)))
            for t in [1,5,10,30,60]:
                ev=s.actual_event.eq(1)&s.actual_latency_s.le(t);pred=s[f'cdf_{t}s']
                for left in [None,0,.2,.4,.6,.8]:
                    keep=np.ones(len(s),bool) if left is None else (pred>=left)&(pred<left+.2+1e-12)
                    cal.append(dict(behavior=b,version=label,cutoff_s=t,bin='all' if left is None else str(left),n=int(keep.sum()),observed=ev[keep].mean(),predicted=pred[keep].mean(),cdf_semantics=time_semantics(b)))
        sensitivity=old[(old.route=='expID')&(old.behavior==b)&(old.model=='window_lognormal_type')]
        for ver in ['exclude_conflicts','time_evidence']:
            z=sensitivity[sensitivity.version==ver]
            if len(z):
                for scope,part in [('version_population',z),('common_evaluable_with_old_filter',z[z.source_row_id.isin(latency_population(d,b,'exclude_conflicts')._source_row_id)])]:
                    scores.append(dict(behavior=b,version='historical_'+ver,route='expID',**oof_summary(part,scope)))
    saveframe(out/'latency_final_vs_sensitivity.csv',scores);saveframe(out/'original_flags_oof_and_reference.csv',pd.concat(all_oof,ignore_index=True));saveframe(out/'latency_final_timepoint_calibration.csv',cal)
    # Window-only route evidence; this does NOT create full latency date OOF.
    window=[];cp=pd.read_csv(S2/'oof_combinations.csv').query("model=='fixed_C1'")
    for route,z in cp.groupby('route'):
        m=marginals(z[['p_'+c for c in COMBOS]].to_numpy())
        for j,b in enumerate(B):
            actual=d.set_index('_source_row_id').loc[z.source_row_id,b+'YesNo'].to_numpy()
            window.append(dict(route=route,behavior=b,n=len(z),event_n=int(actual.sum()),brier=np.mean((actual-m[:,j])**2),binary_nll=np.mean(-actual*np.log(m[:,j])-(1-actual)*np.log1p(-m[:,j])),scope='joint_model_original_flag_window_gate_only_not_full_latency'))
    saveframe(out/'window_gate_validation.csv',window)


def stage2(out):
    assert readj(out/'stage1_metadata.json')['accepted']
    d=load_data();grid,meta,point_combo=grid_points();mp=marginals(point_combo).T
    oldpoint=pd.read_csv(S4/'latency_predictions.csv');old=[]
    for b in B:
        ver='exclude_conflicts' if b=='HeadsUp' else 'original_flags';z=oldpoint[(oldpoint.behavior==b)&(oldpoint.version==ver)&(oldpoint.model=='window_lognormal_type')]
        values=[]
        for _,g in meta.iterrows():values.append(z[(z.call_type==g.call_type)&(z.context==g.context)&(z.distance_m==g.distance_m)].iloc[0][TIME_FIELDS].to_numpy(float))
        old.append(values)
    point=mix_time(np.array(old),mp);ev=evidence(d,grid,meta);ev.to_csv(out/'representative_evidence.csv',index=False)
    paired=pd.read_csv(R2/'R2_2/pattern_adjusted_contrasts.csv').query("resampling_unit=='expID'");point_pp=np.zeros((3,3,2))
    for j,b in enumerate(B):
        for k,t in enumerate(['flat','mod','tv']):
            r=paired[(paired.call_type==t)&(paired.outcome==['H','V','A'][j])].iloc[0];point_pp[j,k]=[r.call_probability,r.control_probability]
    take=np.array([[int(grid.index[grid.CallType==t][0]),int(grid.index[grid.CallType=='control'][0])] for t in ['flat','mod','tv']])
    point_old_pair=np.stack([np.array(old)[j,take,:] for j in range(3)])
    paired_point=mix_time(point_old_pair,point_pp);rows=[];contrasts=[];bootstrap_checks=[]
    for u in UNITS:
        with np.load(S6/f'bootstrap_{u}.npz') as arc:saved={key:arc[key] for key in ['combo','count','time']}
        combo=saved['combo'];p=marginals(combo).transpose(0,2,1)
        updated=mix_time(saved['time'],p)
        # The old conditional CDFs must equal the saved type-only parameters.
        diag={(x['unit'],x['replicate']):x for x in readj(R2/'R2_4/bootstrap_diagnostics.json')}
        maxerr=0.
        for rep in range(500):
            for j,b in enumerate(B):
                a=diag[u,rep]['diagnostics'][j];pars=np.array(a['params']);eta=type_design(grid.CallType)@pars[:-1];pi=a['zero_n']/a['event_n']
                _,lc60,_=time_logs(60,eta,pars[-1],'lognormal')
                for t in [1,5,10,30,60]:
                    _,lct,_=time_logs(t,eta,pars[-1],'lognormal');g=pi+(1-pi)*np.exp(lct-lc60)
                    oldg=saved['time'][rep,j,:,TIME_FIELDS.index(f'cdf_{t}s')]/saved['time'][rep,j,:,0]
                    maxerr=max(maxerr,float(np.max(abs(g-oldg))))
        assert maxerr<1e-7
        bp=np.load(R2/'R2_2'/f'pattern_bootstrap_{u}.npz')['adjusted']
        paired_p=np.stack([bp[...,j+1] for j in range(3)],axis=1)
        paired_old=np.stack([saved['time'][:,j,take,:] for j in range(3)],axis=1)
        updated_pair=mix_time(paired_old,paired_p)
        np.savez_compressed(out/f'bootstrap_final_{u}.npz',combo=combo,count=saved['count'],time=updated,paired_time=updated_pair)
        for j,b in enumerate(B):
            for k in range(36):
                supportrow=ev[(ev.behavior==b)&(ev.grid_row==k)].iloc[0].to_dict()
                for f,field in enumerate(TIME_FIELDS):
                    lo,hi=np.quantile(updated[:,j,k,f],[.025,.975]);rows.append(dict(**supportrow,estimand=field,estimate=point[j,k,f],lower=lo,upper=hi,
                        unit='seconds' if field.endswith('_s') else 'probability',resampling_unit=u,bootstrap_success_n=int(np.isfinite(updated[:,j,k,f]).sum()),bootstrap_total_n=500,
                        interval_kind='pointwise95_fixed_model_parameter_confidence_not_future_prediction',uncertainty_scope='fixed_family_rules_and_reference_not_selection_or_unknown_annotation',model_version='final_original_flags_278'))
            for k,t in enumerate(['flat','mod','tv']):
                for f,field in enumerate(TIME_FIELDS):
                    delta=updated_pair[:,j,k,0,f]-updated_pair[:,j,k,1,f];lo,hi=np.quantile(delta,[.025,.975])
                    contrasts.append(dict(behavior=b,call_type=t,estimand=field,call_estimate=paired_point[j,k,0,f],control_estimate=paired_point[j,k,1,f],difference=paired_point[j,k,0,f]-paired_point[j,k,1,f],
                        lower=lo,upper=hi,reference_pair_n=dict(flat=30,mod=20,tv=39)[t],resampling_unit=u,bootstrap_success_n=500,bootstrap_total_n=500,
                        event_definition=event_id(b),cdf_semantics=time_semantics(b),conditional_time_adjustment='type_only',
                        q4_use='sensitivity_only_no_Control_Approach_time_evidence' if b=='Approach' and field.endswith('_s') else 'keep_event_reference_support_limits',
                        reference_scope='fixed_type_specific_supported_pairs_equal_pair_half_sides',interval_kind='pointwise95_fixed_model_parameter_confidence'))
        bootstrap_checks.append(dict(unit=u,replicates=500,maximum_saved_conditional_CDF_parameter_difference=maxerr,model_fits=0))
    saveframe(out/'latency_original_flags_36.csv',rows);saveframe(out/'latency_original_flags_paired.csv',contrasts)
    saveframe(out/'recombined_bootstrap_checks.csv',bootstrap_checks);revise_oof(out,d)
    snapshot(out,2,dict(accepted=True,fits_performed=0,new_bootstrap_samples=0,replicates_recombined_per_unit=500,full_latency_date_oof_generated=False))
    print('STAGE2 PASS; zero fits; 1000 existing draws recombined; 36 scenarios and matched contrasts',flush=True)


def probability_diagnostic(frame,pv,q,mu,alpha):
    b=frame.VocalNcallsBefore.to_numpy(float);assert (b>=0).all() and np.allclose(b,np.round(b))
    a=np.asarray(alpha);size=1/a;prob=1/(1+a*mu);nz=-np.expm1(-np.log1p(a*mu)/a)
    pinc=q*nbinom.sf(b,size,prob)/nz
    assert (pinc<=q+EPS).all() and np.allclose(pinc[b==0],q[b==0],atol=1e-12)
    r=frame.copy();r['p_V_pattern']=pv;r['q_count_positive']=q;r['p_increase_from_NB2']=pinc
    r['p_V_minus_q']=pv-q;r['p_V_minus_NB2_increase']=pv-pinc
    r['pv_le_q_violated']=pv>q+EPS;r['baseline_zero']=b==0
    r['zero_baseline_identity_violated']=(b==0)&(abs(pv-q)>EPS)
    r['constraints_pass']=~(r.pv_le_q_violated|r.zero_baseline_identity_violated)
    r['same_event_prediction_gap_over_1pp']=abs(pv-pinc)>.01
    r['q4_use']='separate_module_predictions_no_assumed_common_joint_count_behavior_distribution'
    return r


def stage3(out):
    assert readj(out/'stage2_metadata.json')['accepted']
    d=load_data();grid,meta,combo=grid_points();refs=pd.read_csv(out/'final_matched_reference.csv')
    frames=[];g=grid.copy();g['scope']='representative36';g['source_row_id']=np.nan;g['grid_row']=range(36);frames.append(g)
    observed=d.copy();observed['scope']='observed_actual278';observed['source_row_id']=d._source_row_id;observed['grid_row']=np.nan;frames.append(observed)
    for t in ['flat','mod','tv']:
        r=refs[refs.call_type==t].rename(columns={'context':'Context'}).copy()
        for stimulus in [t,'control']:
            x=r.copy();x['CallType']=stimulus;x['scope']='supported_paired_reference';x['comparison_call_type']=t;x['grid_row']=np.nan;frames.append(x)
    query=pd.concat(frames,ignore_index=True)
    # NB2 positive parameters are restored, not re-estimated. Only the unsaved
    # joint C1 and positive-count C1 point gates need their fixed full-data fits.
    pars=[x for x in readj(S3/'fit_diagnostics.json') if x['route']=='full_fit' and x['model']=='hurdle_nb2_full'][0]['params']
    trans,_=matrix_fit(d,'full');eta=matrix_apply(trans,query,'full')@np.array(pars[:-1]);mu=np.exp(eta);alpha=np.exp(pars[-1])
    p=predict_combo(fit_combo(d,1),query);q=binary_gate(d,query,d.VocalNcalls>0);pv=marginals(p)[:,1]
    assert np.allclose(p[:36],combo,atol=1e-10)
    oldcount=pd.read_csv(S3/'count_predictions.csv').query("model=='hurdle_nb2_full'")
    restored=[]
    for _,m in meta.iterrows():restored.append(oldcount[(oldcount.call_type==m.call_type)&(oldcount.context==m.context)&(oldcount.distance_m==m.distance_m)].iloc[0].q_positive)
    assert np.allclose(q[:36],restored,atol=1e-10)
    detail=probability_diagnostic(query[['scope','source_row_id','grid_row','CallType','Context','Distance','Npenguins','VocalNcallsBefore','comparison_call_type']],pv,q,mu,alpha)
    # Existing OOF diagnostic: same fold, existing q, restored positive params.
    co=pd.read_csv(S3/'count_oof.csv').query("route=='expID' and model=='hurdle_nb2_full'").sort_values('source_row_id')
    cp=pd.read_csv(S2/'oof_combinations.csv').query("route=='expID' and model=='fixed_C1'").set_index('source_row_id')
    fd=readj(S3/'fit_diagnostics.json');folds=readj(S1/'metadata.json')['reused_outer_folds'];parts=[]
    for f in folds:
        train=d.iloc[np.array(f['train_rows'])-1];test=d.iloc[np.array(f['test_rows'])-1];z=co.set_index('source_row_id').loc[test._source_row_id]
        pars=np.array([x for x in fd if x['route']=='expID' and x['fold']==f['fold'] and x['model']=='hurdle_nb2_full'][0]['params'])
        tr,_=matrix_fit(train,'full');mm=np.exp(matrix_apply(tr,test,'full')@pars[:-1]);aa=np.exp(pars[-1]);nz=-np.expm1(-np.log1p(aa*mm)/aa)
        assert np.allclose(mm/nz,z.mean_positive,atol=1e-7)
        pp=marginals(cp.loc[test._source_row_id,['p_'+c for c in COMBOS]].to_numpy())[:,1]
        fr=test[COLS].copy();fr['scope']='existing_expID_OOF278';fr['source_row_id']=test._source_row_id;fr['fold']=f['fold']
        parts.append(probability_diagnostic(fr,pp,z.q_positive.to_numpy(),mm,aa))
    detail=pd.concat([detail]+parts,ignore_index=True);detail.to_csv(out/'vocal_cross_module_diagnostic.csv',index=False)
    summary=[]
    for scope,z in detail.groupby('scope'):
        zero=z[z.baseline_zero];bad=z[z.pv_le_q_violated]
        summary.append(dict(scope=scope,n=len(z),baseline_zero_n=len(zero),pv_gt_q_n=int(z.pv_le_q_violated.sum()),
            zero_baseline_identity_violation_n=int(z.zero_baseline_identity_violated.sum()),maximum_positive_pv_minus_q=max(0,z.p_V_minus_q.max()),
            maximum_absolute_pv_minus_q=z.p_V_minus_q.abs().max(),mean_signed_pv_minus_q=z.p_V_minus_q.mean(),
            mean_positive_violation=bad.p_V_minus_q.mean(),maximum_zero_baseline_absolute_gap=zero.p_V_minus_q.abs().max(),
            maximum_absolute_pv_minus_NB2_increase=z.p_V_minus_NB2_increase.abs().max(),mean_absolute_pv_minus_NB2_increase=z.p_V_minus_NB2_increase.abs().mean(),
            same_event_gap_over_1pp_n=int(z.same_event_prediction_gap_over_1pp.sum()),numerical_tolerance=EPS,
            interpretation='diagnosis_only_no_calibration_no_common_joint_count_pattern_distribution'))
    saveframe(out/'vocal_cross_module_summary.csv',summary)
    gaps=[];reps=[]
    for u in UNITS:
        saved=np.load(S6/f'bootstrap_{u}.npz');diff=marginals(saved['combo'])[:,:,1]-saved['count'][:,:,0]
        for k in range(36):
            lo,hi=np.quantile(diff[:,k],[.025,.975]);gaps.append(dict(**meta.iloc[k].to_dict(),grid_row=k,resampling_unit=u,
                p_V_minus_q=pv[k]-q[k],lower=lo,upper=hi,bootstrap_success_n=int(np.isfinite(diff[:,k]).sum()),bootstrap_total_n=500,
                replicate_fraction_pv_gt_q=float((diff[:,k]>EPS).mean()),semantics='exploratory_fixed_model_gap_not_posterior_truth_probability'))
        for k in range(500):reps.append(dict(unit=u,replicate=k,pv_gt_q_n=int((diff[k]>EPS).sum()),zero_baseline_identity_violation_n=int((abs(diff[k])>EPS).sum()),max_abs_gap=float(abs(diff[k]).max())))
    saveframe(out/'vocal_probability_gap_36_intervals.csv',gaps);saveframe(out/'vocal_constraint_bootstrap_diagnostic.csv',reps)
    # English plot states the recorded-time/final-label intersection explicitly.
    figdir=ROOT/'figures/q3/final_revision'/out.name;figdir.mkdir(parents=True,exist_ok=True)
    fig,axes=plt.subplots(1,2,figsize=(11,4))
    for t in TYPES:
        z=detail[(detail.scope=='representative36')&(detail.CallType==t)]
        axes[0].scatter(z.q_count_positive,z.p_V_pattern,label=t,s=25)
    axes[0].plot([0,.8],[0,.8],'k--',lw=.8);axes[0].set_xlabel('Count model: P(N after > 0)');axes[0].set_ylabel('Pattern: P(final vocal-increase label = 1)');axes[0].legend()
    tt=pd.read_csv(out/'latency_original_flags_36.csv').query("resampling_unit=='expID' and behavior=='Vocal' and context=='after' and distance_m==100")
    for t in TYPES:
        z=tt[(tt.call_type==t)&tt.estimand.isin([f'cdf_{x}s' for x in [1,5,10,30,60]])].copy();z['t']=z.estimand.str.extract(r'(\d+)').astype(int);z=z.sort_values('t');axes[1].plot(z.t,z.estimate,'o-',label=t)
    axes[1].set_xlabel('Recorded vocal time threshold t (s)');axes[1].set_ylabel('P(final increase label = 1 and recorded time <= t)');axes[1].set_title('Not time of first baseline crossing',fontsize=10);axes[1].legend()
    fig.tight_layout();fig.savefig(figdir/'vocal_semantics_and_consistency.png',dpi=180);plt.close(fig)
    snapshot(out,3,dict(accepted=True,necessary_fixed_point_gate_fits=2,NB2_positive_component_refits=0,time_model_refits=0,calibration_applied=False,old_36_point_predictions_reproduced=True))
    print(pd.DataFrame(summary).to_string(index=False),flush=True)


def stage4(out):
    assert readj(out/'stage3_metadata.json')['accepted']
    d=load_data();grid,meta,combo=grid_points()
    diag=pd.read_csv(out/'vocal_cross_module_diagnostic.csv').query("scope=='representative36'")
    sidecar=diag[['grid_row','p_V_pattern','q_count_positive','p_increase_from_NB2','p_V_minus_q','p_V_minus_NB2_increase','pv_le_q_violated','zero_baseline_identity_violated','constraints_pass']].copy()
    sidecar['common_joint_count_pattern_distribution_available']=False
    time=pd.read_csv(out/'latency_original_flags_36.csv').merge(sidecar,on='grid_row',validate='many_to_one')
    time['cdf_semantics']=time.behavior.map(time_semantics)
    time['conditional_time_information_required']=~time.estimand.isin(['p_response','mass_no_response','cdf_60s'])
    pure_probability=~time.conditional_time_information_required
    time.loc[pure_probability,'availability']='exploratory_original_flag_probability_keep_joint_support'
    borrowed=time.conditional_time_information_required & time.positive_time_type_n.eq(0)
    time.loc[borrowed,'availability']='conditional_time_model_borrowed_sensitivity_only'
    time['within_HVA_probability_coherence_pass']=True
    time['Q4_cross_module_use']='separate_module_inputs_only_not_a_coherent_joint_count_and_HVA_model'
    time.to_csv(out/'q4_latency_original_flags_36.csv',index=False)
    combinations=pd.read_csv(S6/'combination_predictions.csv',dtype={'combo':str})
    key=['call_type','context','distance_m']
    m=meta[key].copy();m['grid_row']=range(36)
    combinations=combinations.merge(m,on=key,validate='many_to_one').merge(sidecar,on='grid_row',validate='many_to_one')
    combinations['event_definition']='original_HVA_V_equals_N_after_gt_N_before_in_this_file'
    combinations['zero_state_semantics']='none_of_original_flags_not_no_actual_calls_or_no_perception'
    combinations['model_population_n']=278
    combinations.to_csv(out/'q4_combination_original_flags_36.csv',index=False)
    count=pd.read_csv(S6/'latency_intensity_predictions.csv').query("outcome=='VocalNcalls'")
    count=count.merge(m,on=key,validate='many_to_one').merge(sidecar,on='grid_row',validate='many_to_one')
    count['count_event_definition']='actual_N_after_positive_not_original_V_label'
    count['Q4_cross_module_use']='standalone_count_distribution_do_not_replace_HVA_marginal'
    count.to_csv(out/'q4_count_reused_36.csv',index=False)
    duration=[]
    for _,g in meta.iterrows():
        for b in ['HeadsUp','Approach']:duration.append(dict(**g.to_dict(),behavior=b,estimand='true_behavior_duration',estimate=np.nan,lower=np.nan,upper=np.nan,unit='seconds',availability='not_identified_60_encoding_unresolved'))
    saveframe(out/'q4_duration_unavailable.csv',duration)
    # A readable scientific result index, with primary vs conditional quantities.
    p=pd.read_csv(out/'latency_original_flags_paired.csv');p['module']='Latency';p['primary']=p.estimand.eq('p_response');p['model_population_n']=278
    countp=pd.read_csv(R2/'R2_3/count_paired_contrasts.csv');countp['module']='Intensity';countp['primary']=countp.estimand.eq('mean_total');countp['model_population_n']=278
    pat=pd.read_csv(R2/'R2_2/pattern_adjusted_contrasts.csv');pat['module']='Pattern';pat['primary']=pat.outcome.eq('any');pat['model_population_n']=278
    pat['estimand']=pat.outcome;pat['difference']=pat.probability_difference
    pd.concat([pat,countp,p],ignore_index=True).to_csv(out/'final_scientific_result_index.csv',index=False)
    manifest=[]
    files=[('joint_HVA','q4_combination_original_flags_36.csv','original_HVA_278','formal_exploratory_joint_flags_only'),
        ('Latency','q4_latency_original_flags_36.csv','original_flags_278','window_primary_conditional_time_evidence_flags_required'),
        ('Count','q4_count_reused_36.csv','actual_count_278','standalone_NB2_not_calibrated_to_joint_flags'),
        ('matched_contrasts','latency_original_flags_paired.csv','original_flags_278_supported_pairs30_20_39','fixed_matched_reference_not_36_grid'),
        ('Duration','q4_duration_unavailable.csv','unknown_observation_mechanism','no_formal_numeric_input'),
        ('cross_module_check','vocal_cross_module_diagnostic.csv','point_conditions_and_existing_OOF','mandatory_constraint_diagnostic_no_correction'),
        ('representative_evidence','representative_evidence.csv','original_flags_278','mandatory_support_positive_time_evidence_sidecar')]
    for module,name,pop,use in files:
        src=out/name;manifest.append(dict(module=module,path=str(src.relative_to(ROOT)),sha256=sha(src),population=pop,use=use,
            version='final_original_flags_278',uncertainty='fixed_model_pointwise95_not_selection_not_future_prediction',vocal_cdf_semantics=SEMANTICS))
    for u in UNITS:
        src=out/f'bootstrap_final_{u}.npz';manifest.append(dict(module='joint_parameter_repeats',path=str(src.relative_to(ROOT)),sha256=sha(src),population='as_labelled',use='align_same_unit_and_replicate_preserve_joint_HVA_do_not_invent_joint_count_HVA',version='final_original_flags_278',uncertainty='500_fixed_model_replicates_'+u))
    for module,src,use in [('count_paired_reused',R2/'R2_3/count_paired_contrasts.csv','actual_counts_not_original_V_label'),
            ('Q4_semantics_notes',out/'Q4_FINAL_INPUT_NOTES.md','mandatory_semantics_availability_and_cross_module_restrictions'),
            ('paper_text',ROOT/'paper/latex/q3_final_revision.tex','English_fragment_not_compiled_or_merged_into_template')]:
        if src.exists():manifest.append(dict(module=module,path=str(src.relative_to(ROOT)),sha256=sha(src),population='as_labelled',use=use,version='final_revision_evidence'))
    manifest.append(dict(module='future_latency_prediction_ranges',path=str((S6/'future_experiment_prediction_intervals.csv').relative_to(ROOT)),sha256=sha(S6/'future_experiment_prediction_intervals.csv'),population='historical_filtered_time',use='NOT_UPDATED_NOT_FINAL_ORIGINAL_FLAG_VA_FUTURE_PREDICTION',version='historical_only',uncertainty='no_new_original_flag_latency_prediction_intervals'))
    saveframe(out/'q4_final_input_manifest.csv',manifest)
    # Independent interval recalculation and unchanged historical-file checks.
    acceptance=dict(numerical_interface_pass=True,original_flags_population_n=278,original_raw_sha256=sha(INPUT),
        OOF_gate_same_fold_pass=True,bootstrap_equivalence_checks=3000,probability_calibration_applied=False,
        cross_module_constraints_pass=bool(diag.constraints_pass.all()),common_joint_count_HVA_distribution_available=False,
        formal_duration_identified=False,future_latency_prediction_intervals_updated=False,software_pass_is_not_scientific_validity=True)
    T=pd.read_csv(out/'latency_original_flags_36.csv');P=pd.read_csv(out/'latency_original_flags_paired.csv')
    for u in UNITS:
        with np.load(out/f'bootstrap_final_{u}.npz') as arc:a=arc['time'];c=arc['combo'];b=arc['paired_time']
        assert np.allclose(c.sum(-1),1) and np.allclose(a[:,:,:,0],marginals(c).transpose(0,2,1))
        assert np.allclose(a[:,:,:,TIME_FIELDS.index('cdf_60s')],a[:,:,:,0])
        for j,behavior in enumerate(B):
            for k in range(36):
                z=T[(T.resampling_unit==u)&(T.behavior==behavior)&(T.grid_row==k)].set_index('estimand')
                for f,field in enumerate(TIME_FIELDS):assert np.allclose(z.loc[field,['lower','upper']].to_numpy(float),np.quantile(a[:,j,k,f],[.025,.975]))
            for k,typ in enumerate(['flat','mod','tv']):
                z=P[(P.resampling_unit==u)&(P.behavior==behavior)&(P.call_type==typ)].set_index('estimand')
                for f,field in enumerate(TIME_FIELDS):assert np.allclose(z.loc[field,['lower','upper']].to_numpy(float),np.quantile(b[:,j,k,0,f]-b[:,j,k,1,f],[.025,.975]))
        original=np.load(S6/f'bootstrap_{u}.npz');assert np.array_equal(c,original['combo'])
    acceptance['all_saved_time_and_paired_intervals_recalculated']=True;acceptance['joint_probabilities_unchanged']=True
    historical=readj(out/'historical_hashes.json');assert all((ROOT/p).exists() and sha(ROOT/p)==h for p,h in historical.items())
    acceptance['historical_files_unchanged']=len(historical)
    writej(out/'final_acceptance.json',acceptance)
    snapshot(out,4,dict(accepted=True,new_model_search=False,new_fits_in_stage=0,scientific_cross_module_incoherence_disclosed=True))
    print('STAGE4 numerical/interface PASS; historical files unchanged',len(historical),'cross-module constraints pass',acceptance['cross_module_constraints_pass'],flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',type=int);parser.add_argument('--run');args=parser.parse_args()
    folder=Path(args.run).resolve() if args.run else ROOT/'results/q3/final_revision'/datetime.now(timezone.utc).strftime('q3_final_%Y%m%dT%H%M%SZ')
    with threadpool_limits(limits=1):
        if args.stage==1:stage1(folder)
        elif args.stage==2:stage2(folder)
        elif args.stage==3:stage3(folder)
        elif args.stage==4:stage4(folder)
        else:raise ValueError('Stage not implemented yet')
