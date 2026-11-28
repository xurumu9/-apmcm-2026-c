"""Q3 stage 6. Paired/track cluster bootstrap of fixed exploratory models.

No original files overwritten; no no-response latency imputation; no git writes.
"""
import argparse
import hashlib
import json
import subprocess
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
import sklearn
from scipy.stats import nbinom
from threadpoolctl import threadpool_limits

from q3_playback_analysis import ROOT, INPUT, COLS, COMBOS, TYPES, fit_combo, predict_combo, combo, plt
from q3_count_latency_models import (STAGE1, fit_count, predict_count, fit_time, predict_time,
                                    latency_population, matrix_apply, time_quantile)
from q3_revised_models import support

SEED=20261127
BEHAVIORS=['HeadsUp','Vocal','Approach']
COUNT_FIELDS=['q_positive','mean_positive','mean_total','median_total']
TIME_FIELDS=['p_response','mass_no_response','mass_recorded_zero','mass_positive','pi_zero_given_response',
             'conditional_mean_s','conditional_median_s','positive_mean_s','positive_median_s',
             'cdf_1s','cdf_5s','cdf_10s','cdf_30s','cdf_60s']
UNITS=['expID','natural_track']
_DATA=None
_GRID=None
_DRAWS=100


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load_data():
    d=pd.read_csv(INPUT)
    d['_source_row_id']=d.index+1;d['_source_exp_id']=d.expID
    tracks=d[d.Type=='call'].set_index('expID').PlaybackTrack
    assert tracks.index.is_unique and len(tracks)==139
    d['_natural_track']=d.expID.map(tracks)
    assert d['_natural_track'].notna().all()
    return d


def grid_from(stage1):
    s=pd.read_csv(stage1/'representative_support.csv')
    g=s[s.analysis_population_id=='combo_all_v1'].reset_index(drop=True)
    x=pd.DataFrame(dict(CallType=g.call_type,Context=g.context,Distance=g.distance_m,
        Npenguins=g.n_penguins,VocalNcallsBefore=g.vocal_ncalls_before,expID=-1,VocalNcalls=0))
    return x,s


def resample(d,unit,replicate):
    u=UNITS.index(unit)
    rng=np.random.default_rng(np.random.SeedSequence([SEED,u,replicate,0]))
    key='expID' if unit=='expID' else '_natural_track'
    labels=d[key].drop_duplicates().to_numpy()
    chosen=rng.choice(labels,len(labels),replace=True)
    parts=[];next_id=0
    for slot,label in enumerate(chosen):
        part=d[d[key]==label].copy()
        ids=part.expID.drop_duplicates().tolist();mapping={e:next_id+j for j,e in enumerate(ids)}
        part['expID']=part.expID.map(mapping);next_id+=len(ids)
        part['_bootstrap_cluster_id']=slot
        parts.append(part)
    sampled=pd.concat(parts,ignore_index=True)
    assert (sampled.groupby('expID').size()==2).all()
    assert (sampled.groupby('expID').Type.nunique()==2).all()
    return sampled,chosen.tolist()


def draw_counts(train,grid,fit,pred,rng,draws):
    trans,pars,_=fit
    mu=np.exp(matrix_apply(trans,grid,'full')@pars[:-1]);alpha=np.exp(pars[-1])
    size=1/alpha;prob=1/(1+alpha*mu);p0=nbinom.pmf(0,size,prob)
    active=rng.random((draws,len(grid)))<pred.q_positive.to_numpy()
    target=p0[None,:]+rng.random(active.shape)*(1-p0[None,:])
    target=np.minimum(target,np.nextafter(1.,0.))
    positive=np.maximum(1,nbinom.ppf(target,size,prob))
    result=np.where(active,positive,0.)
    assert np.isfinite(result).all() and (result>=0).all()
    return result


def draw_times(grid,fit,pred,rng,draws):
    trans,pars,_=fit;eta=matrix_apply(trans,grid,'type')@pars[:-1]
    u=rng.random((draws,len(grid)))
    mass0=pred.mass_recorded_zero.to_numpy();p=pred.p_response.to_numpy()
    # Kind 0=no response (time NaN), 1=recorded zero, 2=positive time.
    kind=np.where(u<mass0,1,np.where(u<p,2,0)).astype(np.int8)
    positive=time_quantile(np.maximum(rng.random(kind.shape),np.nextafter(0.,1.)),eta[None,:],pars[-1],'lognormal')
    time=np.where(kind==0,np.nan,np.where(kind==1,0.,positive))
    assert np.all((time[np.isfinite(time)]>=0)&(time[np.isfinite(time)]<=60+1e-8))
    return time,kind


def fit_fixed(train,grid,unit,replicate,draws):
    rng=np.random.default_rng(np.random.SeedSequence([SEED,UNITS.index(unit),replicate+1,1]))
    result=dict(unit=unit,replicate=replicate,combo=np.full((36,8),np.nan),count=np.full((36,4),np.nan),
        time=np.full((3,36,len(TIME_FIELDS)),np.nan),parameters=np.full(4,np.nan),
        count_draws=np.full((draws,36),np.nan),time_draws=np.full((3,draws,36),np.nan),
        time_kind=np.full((3,draws,36),-1,dtype=np.int8),diagnostics=[])
    missing=sorted(set(COMBOS)-set(combo(train)))
    for component in ['combo','count']+BEHAVIORS:
        diag=dict(unit=unit,replicate=replicate,component=component,success=False,reason='',bound_hit=[],
            train_n=len(train),event_n=None,positive_n=None,zero_n=None,absent_call_types=sorted(set(TYPES)-set(train.CallType)),
            missing_combos=missing if component=='combo' else [],warnings=[])
        try:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always')
                if component=='combo':
                    p=predict_combo(fit_combo(train,1),grid)
                    assert np.isfinite(p).all() and np.allclose(p.sum(1),1)
                    result['combo']=p
                elif component=='count':
                    diag['event_n']=int((train.VocalNcalls>0).sum());diag['positive_n']=diag['event_n']
                    if not diag['positive_n']:
                        diag['reason']='missing_positive_events';raise ValueError('No positive counts')
                    fit=fit_count(train,'nb2','full');diag['bound_hit']=fit[2]['bound_hit']
                    if not fit[2]['success']:raise RuntimeError(fit[2]['message'])
                    pred=predict_count(train,grid,'nb2','full',fit)
                    assert np.isfinite(pred[COUNT_FIELDS]).all().all()
                    result['count']=pred[COUNT_FIELDS].to_numpy();result['parameters'][0]=fit[2]['alpha']
                    result['count_draws']=draw_counts(train,grid,fit,pred,rng,draws)
                else:
                    b=component;j=BEHAVIORS.index(b);pop=latency_population(train,b,'exclude_conflicts')
                    diag.update(train_n=len(pop),event_n=int(pop['_event'].sum()),
                        positive_n=int(((pop['_event']==1)&(pop[b+'Latency']>0)).sum()),
                        zero_n=int(((pop['_event']==1)&(pop[b+'Latency']==0)).sum()))
                    diag['absent_positive_types']=sorted(set(TYPES)-set(pop.loc[(pop['_event']==1)&(pop[b+'Latency']>0),'CallType']))
                    if not diag['positive_n']:
                        diag['reason']='missing_positive_events';raise ValueError('No positive times')
                    fit=fit_time(pop,b,'lognormal','type','window');diag['bound_hit']=fit[2]['bound_hit']
                    if not fit[2]['success']:raise RuntimeError(fit[2]['message'])
                    test=grid.copy();test['_event']=0;test[b+'Latency']=np.nan
                    pred=predict_time(pop,test,b,'lognormal','type','window','exclude_conflicts',fit)
                    assert np.isfinite(pred[TIME_FIELDS]).all().all()
                    result['time'][j]=pred[TIME_FIELDS].to_numpy();result['parameters'][j+1]=np.exp(fit[1][-1])
                    result['time_draws'][j],result['time_kind'][j]=draw_times(test,fit,pred,rng,draws)
                diag['warnings']=[str(w.message) for w in caught]
            diag['success']=True;diag['reason']='ok'
        except Exception as exc:
            if not diag['reason']:diag['reason']='numerical_failure'
            diag['error']=f'{type(exc).__name__}: {exc}'
            # All failed-component outputs remain unusable, including partial calculations.
            if component=='combo':result['combo'][:]=np.nan
            elif component=='count':
                result['count'][:]=np.nan;result['parameters'][0]=np.nan;result['count_draws'][:]=np.nan
            else:
                j=BEHAVIORS.index(component);result['time'][j]=np.nan;result['parameters'][j+1]=np.nan
                result['time_draws'][j]=np.nan;result['time_kind'][j]=-1
        result['diagnostics'].append(diag)
    return result


def worker_init(data,grid,draws):
    global _DATA,_GRID,_DRAWS
    _DATA=data;_GRID=grid;_DRAWS=draws


def worker(task):
    unit,replicate=task
    with threadpool_limits(limits=1):
        d,chosen=resample(_DATA,unit,replicate)
        r=fit_fixed(d,_GRID,unit,replicate,_DRAWS)
        r['sampling']=dict(unit=unit,replicate=replicate,sampled_units=chosen,sampled_rows_n=len(d),
            source_exp_n=int(d['_source_exp_id'].nunique()),new_pair_n=int(d.expID.nunique()))
        return r


def interval(samples,total):
    good=np.asarray(samples);good=good[np.isfinite(good)];n=len(good)
    lo,hi=np.quantile(good,[.025,.975]) if n else [np.nan,np.nan]
    return dict(lower=lo,upper=hi,bootstrap_success_n=n,bootstrap_total_n=total,
        interval_scope='all_requested_replicates' if n==total else 'conditional_on_successful_replicates_no_unconditional_coverage_claim')


def context_row(support_table,population,k):
    return support_table[support_table.analysis_population_id==population].iloc[k].to_dict()


def component_counts(diags,component):
    sub=[x for x in diags if x['component']==component]
    return dict(missing_event_n=sum(x['reason']=='missing_positive_events' for x in sub),
        numerical_failure_n=sum(x['reason']=='numerical_failure' for x in sub),
        bound_fit_n=sum(bool(x['bound_hit']) for x in sub))


def write_delivery(out,d,grid,support_table,point,results,total,draws,stage5):
    combos=[];canonical=[];predictions=[];sets=[];contrasts=[];params=[];diagnostics=[]
    combo_index={tuple(grid.loc[k,['CallType','Context','Distance']]):k for k in grid.index}
    for unit in UNITS:
        reps=sorted([r for r in results if r['unit']==unit],key=lambda r:r['replicate'])
        bc=np.stack([r['combo'] for r in reps]);bn=np.stack([r['count'] for r in reps]);bt=np.stack([r['time'] for r in reps]);bp=np.stack([r['parameters'] for r in reps])
        cd=np.stack([r['count_draws'] for r in reps]);td=np.stack([r['time_draws'] for r in reps]);tk=np.stack([r['time_kind'] for r in reps])
        np.savez_compressed(out/f'bootstrap_{unit}.npz',combo=bc,count=bn,time=bt,parameters=bp,count_draws=cd,time_draws=td,time_kind=tk)
        diags=[x for r in reps for x in r['diagnostics']];diagnostics.extend(diags)
        common=dict(resampling_unit=unit,uncertainty_scope='fixed_models_and_analysis_rules_not_model_selection',
            confidence_level=.95,interval_method='pointwise_cluster_bootstrap_percentile',model_version='stage6_fixed_v1',
            bootstrap_total_n=total,bootstrap_draws_per_replicate=draws)
        for k in range(36):
            base=context_row(support_table,'combo_all_v1',k)
            base.update(common);base['extrapolated_distance']=base['distance_support']=='extrapolation'
            for j,c in enumerate(COMBOS):
                row=dict(**base,combo=c,probability=point['combo'][k,j],**component_counts(diags,'combo'))
                row.update(interval(bc[:,k,j],total));row['missing_training_class_n']=sum(c in x['missing_combos'] for x in diags if x['component']=='combo')
                combos.append(row)
            mix=np.nanmean(bc[:,k,:],axis=0);order=np.argsort(-mix,kind='stable');n=int(np.searchsorted(np.cumsum(mix[order]),.95)+1)
            sets.append(dict(**base,estimand='future_HVA_category',prediction_set='|'.join(COMBOS[j] for j in order[:n]),
                set_size=n,model_mixture_coverage=float(mix[order[:n]].sum()),
                predictive_method='95pct_highest_mixture_probability_set_not_externally_calibrated',
                **{'mixture_p_'+c:mix[j] for j,c in enumerate(COMBOS)}))
            sets[-1].pop('confidence_level',None);sets[-1].pop('interval_method',None)
            sets[-1]['predictive_coverage_level']=.95
            sets[-1]['bootstrap_success_n']=int(np.isfinite(bc[:,k,:]).all(axis=1).sum())
            for field_index,field in enumerate(COUNT_FIELDS):
                s=context_row(support_table,'count_actual_v1',k)
                s.update(common);s.update(component_counts(diags,'count'));s.update(interval(bn[:,k,field_index],total))
                cell=d[(d.CallType==s['call_type'])&(d.Context==s['context'])&(d.VocalNcalls>0)]
                s.update(behavior='Vocal',outcome='VocalNcalls',estimand=field,estimate=point['count'][k,field_index],
                    unit='probability' if field=='q_positive' else 'count',event_definition_id='actual_count_positive',
                    analysis_rule='count_actual_v1',positive_n=len(cell),
                    conditional_joint_support=support(cell[COLS[2:]].to_numpy(float),np.array([s['distance_m'],8,0])),
                    availability='exploratory_fixed_model',extrapolated_distance=s['distance_support']=='extrapolation')
                canonical.append(s)
            finite=cd[:,:,k];finite=finite[np.isfinite(finite)]
            lo,hi=np.quantile(finite,[.025,.975],method='inverted_cdf') if len(finite) else [np.nan,np.nan]
            s=context_row(support_table,'count_actual_v1',k)
            predictions.append(dict(**s,resampling_unit=unit,behavior='Vocal',outcome='VocalNcalls',
                estimand='future_total_count_in_60s_including_zero',prediction_lower=lo,prediction_upper=hi,
                predictive_valid_n=len(finite),predictive_requested_n=total*draws,
                predictive_method='bootstrap_parameter_mixture_plus_observation_draws',
                uncertainty_scope='fixed_models_and_analysis_rules_not_model_selection',predictive_coverage_level=.95,
                bootstrap_total_n=total,bootstrap_success_n=int(np.isfinite(cd[:,:,k]).all(axis=1).sum())))
            for j,b in enumerate(BEHAVIORS):
                pop=latency_population(d,b,'exclude_conflicts')
                base=context_row(support_table,f'latency_{b}_v1',k)
                cell=pop[(pop.CallType==base['call_type'])&(pop.Context==base['context'])]
                positive=cell[(cell['_event']==1)&(cell[b+'Latency']>0)]
                base.update(common);base.update(component_counts(diags,b))
                base.update(behavior=b,outcome=b+'Latency',analysis_rule=f'latency_{b}_exclude_conflicts_v1',
                    event_definition_id='original_behavior_flag_in_evaluable_population',positive_n=len(positive),
                    conditional_joint_support=support(positive[COLS[2:]].to_numpy(float),np.array([base['distance_m'],8,0])),
                    positive_time_evidence='observed_in_cell' if len(positive) else 'none_in_cell_model_borrows_other_cells',
                    availability='exploratory_fixed_model',extrapolated_distance=base['distance_support']=='extrapolation')
                for q,field in enumerate(TIME_FIELDS):
                    row=dict(**base,estimand=field,estimate=point['time'][j,k,q],unit='s' if field.endswith('_s') else 'probability')
                    row.update(interval(bt[:,j,k,q],total));canonical.append(row)
                kind=tk[:,j,:,k].reshape(-1);time=td[:,j,:,k].reshape(-1);responsive=time[kind>0]
                lo,hi=np.quantile(responsive,[.025,.975]) if len(responsive) else [np.nan,np.nan]
                valid=kind>=0
                pred=dict(**base,estimand='future_latency_conditional_on_response_within60_including_recorded_zero',
                    prediction_lower=lo,prediction_upper=hi,predictive_valid_n=int(valid.sum()),
                    predictive_requested_n=total*draws,predictive_response_draws_n=len(responsive),
                    predictive_no_response_probability=float(np.mean(kind[valid]==0)) if valid.any() else np.nan,
                    predictive_recorded_zero_probability=float(np.mean(kind[valid]==1)) if valid.any() else np.nan,
                    predictive_method='bootstrap_parameter_mixture_plus_observation_draws',
                    conditional_simulation_quality='limited_response_draws' if len(responsive)<200 else 'response_draws_ge200',
                    nonresponse_time_encoding='NaN with separate kind=0; never an observed time60')
                # Prediction limits are separate from base confidence-interval metadata.
                pred.pop('confidence_level',None);pred.pop('interval_method',None)
                pred['predictive_coverage_level']=.95
                pred['bootstrap_success_n']=int((tk[:,j,:,k]>=0).all(axis=1).sum())
                predictions.append(pred)
            if grid.CallType.iloc[k]!='control':
                ci=combo_index[('control',grid.Context.iloc[k],grid.Distance.iloc[k])]
                for j,c in enumerate(COMBOS):
                    delta=bc[:,k,j]-bc[:,ci,j]
                    row=dict(**context_row(support_table,'combo_all_v1',k),resampling_unit=unit,combo=c,
                        estimate=point['combo'][k,j]-point['combo'][ci,j],estimand='model_probability_difference_call_minus_control',
                        control_joint_support=context_row(support_table,'combo_all_v1',ci)['joint_support'],
                        uncertainty_scope='fixed_models_and_analysis_rules_not_model_selection',interpretation='model_contrast_not_causal_effect',
                        interval_method='pointwise_cluster_bootstrap_percentile',confidence_level=.95)
                    row.update(interval(delta,total));contrasts.append(row)
        for j,name in enumerate(['NB2_alpha','HeadsUp_logtime_sigma','Vocal_logtime_sigma','Approach_logtime_sigma']):
            row=dict(**common,parameter=name,estimate=point['parameters'][j],**component_counts(diags,(['count']+BEHAVIORS)[j]))
            row.update(interval(bp[:,j],total));params.append(row)
    pd.DataFrame(combos).to_csv(out/'combination_predictions.csv',index=False)
    table=pd.DataFrame(canonical)
    duration=pd.read_csv(stage5/'duration_availability.csv').rename(columns={'model_version':'duration_model_version'})
    duration['outcome']=duration.behavior+'Duration';duration['unit']='s';duration['resampling_unit']='not_applicable'
    duration['uncertainty_scope']='not_identified';table=pd.concat([table,duration],ignore_index=True)
    table.to_csv(out/'latency_intensity_predictions.csv',index=False)
    pd.DataFrame(predictions).to_csv(out/'future_experiment_prediction_intervals.csv',index=False)
    pd.DataFrame(sets).to_csv(out/'combination_future_prediction_sets.csv',index=False)
    pd.DataFrame(contrasts).to_csv(out/'representative_call_control_contrasts.csv',index=False)
    pd.DataFrame(params).to_csv(out/'parameter_confidence_intervals.csv',index=False)
    pd.DataFrame(diagnostics).to_json(out/'bootstrap_diagnostics.json',orient='records',indent=2)
    pd.DataFrame([r['sampling'] for r in results]).to_json(out/'resampling_manifest.json',orient='records',indent=2)
    summary=[]
    for unit in UNITS:
        for component in ['combo','count']+BEHAVIORS:
            subset=[x for x in diagnostics if x['unit']==unit and x['component']==component]
            summary.append(dict(resampling_unit=unit,component=component,total_n=len(subset),success_n=sum(x['success'] for x in subset),
                **component_counts(subset,component),warnings_n=sum(bool(x['warnings']) for x in subset),
                absent_training_type_n=sum(bool(x['absent_call_types']) for x in subset),
                missing_combo001_n=sum('001' in x['missing_combos'] for x in subset)))
    pd.DataFrame(summary).to_csv(out/'bootstrap_summary.csv',index=False)
    return table,pd.DataFrame(combos),pd.DataFrame(summary)


def plot_delivery(figdir,table,combos):
    fig,axes=plt.subplots(1,2,figsize=(11,4))
    for ax,unit in zip(axes,UNITS):
        sub=combos[(combos.resampling_unit==unit)&(combos.context=='searching')&(combos.combo=='000')]
        for typ in TYPES:
            s=sub[sub.call_type==typ].sort_values('distance_m')
            ax.plot(s.distance_m,1-s.probability,'o-',label=typ)
            ax.fill_between(s.distance_m,1-s.upper,1-s.lower,alpha=.15)
        ax.set(title=f'{unit}: searching, N=8',xlabel='Distance (m)',ylabel='Any-response probability',ylim=(0,1));ax.legend()
    fig.tight_layout();fig.savefig(figdir/'response_uncertainty.png',dpi=220);plt.close(fig)


def run(args):
    stage1=args.stage1 if args.stage1.is_absolute() else ROOT/args.stage1
    stage5=args.stage5 if args.stage5.is_absolute() else ROOT/args.stage5
    d=load_data();g,s=grid_from(stage1)
    smeta=json.loads((stage1/'metadata.json').read_text());assert sha(INPUT)==smeta['input_sha256']
    stamp=datetime.now(timezone.utc).strftime('q3_stage6_'+args.label+'_%Y%m%dT%H%M%SZ')
    out=ROOT/'results/q3'/stamp;out.mkdir(parents=True,exist_ok=False)
    figdir=ROOT/'figures/q3'/stamp;figdir.mkdir(parents=True,exist_ok=False)
    with threadpool_limits(limits=1):point=fit_fixed(d,g,'expID',-1,args.predictive_draws)
    assert all(x['success'] for x in point['diagnostics']),point['diagnostics']
    (out/'point_fit_diagnostics.json').write_text(json.dumps(point['diagnostics'],indent=2),encoding='utf-8')
    results=[];tasks=[(unit,b) for unit in UNITS for b in range(args.replicates)]
    with ProcessPoolExecutor(max_workers=args.workers,initializer=worker_init,initargs=(d,g,args.predictive_draws)) as pool:
        pending=[pool.submit(worker,t) for t in tasks]
        for future in as_completed(pending):
            results.append(future.result())
            if len(results)%25==0 or len(results)==len(tasks):
                print('BOOTSTRAP',len(results),'/',len(tasks),flush=True)
                (out/'progress.json').write_text(json.dumps(dict(completed=len(results),requested=len(tasks))),encoding='utf-8')
    results.sort(key=lambda r:(UNITS.index(r['unit']),r['replicate']))
    table,combos,summary=write_delivery(out,d,g,s,point,results,args.replicates,args.predictive_draws,stage5)
    plot_delivery(figdir,table,combos)
    # Consolidate prior held-out scores without refitting or relabeling their targets.
    stages={'2':'q3_stage2_20261127T115748Z','3':'q3_stage3_20261127T125020Z','4':'q3_stage4_20261127T125945Z','5':stage5.name}
    frames=[]
    for stage,name in stages.items():
        p=ROOT/'results/q3'/name/'validation.csv';v=pd.read_csv(p);v['stage']=stage;v['source_run']=name;frames.append(v)
    pd.concat(frames,ignore_index=True).to_csv(out/'validation_evidence.csv',index=False)
    prior_gee=ROOT/'results/q3'/stages['2']/'gee_associations.csv'
    gee=pd.read_csv(prior_gee);gee['interval_method']='GEE_expID_robust_sandwich_not_bootstrap';gee.to_csv(out/'gee_parameter_intervals.csv',index=False)
    head=subprocess.run(['git','-c',f'safe.directory={ROOT.as_posix()}','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True).stdout.strip()
    meta=dict(run_id=stamp,git_head=head,working_tree='uncommitted implementation',input_sha256=sha(INPUT),script_sha256=sha(__file__),
        helper_sha256={n:sha(ROOT/'src/python'/n) for n in ['q3_playback_analysis.py','q3_revised_models.py','q3_count_latency_models.py']},
        stage1_run=str(stage1.relative_to(ROOT)),stage5_run=str(stage5.relative_to(ROOT)),replicates_per_unit=args.replicates,
        predictive_draws_per_replicate=args.predictive_draws,seed=SEED,workers=args.workers,blas_threads_per_worker=1,
        versions=dict(numpy=np.__version__,pandas=pd.__version__,scipy=scipy.__version__,sklearn=sklearn.__version__),
        source_cluster_n=dict(expID=int(d.expID.nunique()),natural_track=int(d['_natural_track'].nunique())),
        fixed_models=dict(combo='C1',count='hurdle_NB2_full',latency='window_lognormal_type_exclude_conflicts'),
        uncertainty_scope='fixed_models_and_analysis_rules_not_model_selection',interval_method='pointwise_cluster_bootstrap_percentile_95',
        full_analysis=args.replicates>=500,label=args.label,figure_dir=str(figdir.relative_to(ROOT)),
        formal_duration_model_ready=False,duration_encoding_verified=False,
        limits=['prior data exploration; no independent test set','rare state 001 only one observed record',
                'track IDs may share underlying recording','date dependence not jointly resampled',
                'conditional latent populations differ; no response is not no perception','duration encoding unresolved',
                'predictive intervals and sets are model-based, not externally calibrated'])
    (out/'metadata.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    (out/'implementation_snapshot.py').write_bytes(Path(__file__).read_bytes())
    print('STAGE6',out);print(summary.to_string(index=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stage1',type=Path,default=STAGE1)
    p.add_argument('--stage5',type=Path,default=ROOT/'results/q3/q3_stage5_20261127T131905Z')
    p.add_argument('--replicates',type=int,default=500);p.add_argument('--workers',type=int,default=2)
    p.add_argument('--predictive-draws',type=int,default=100);p.add_argument('--label',default='full')
    args=p.parse_args();assert args.replicates>0 and args.workers>0 and args.predictive_draws>0
    run(args)
