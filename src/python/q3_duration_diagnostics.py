"""Q3 stage 5: raw-record audit and explicitly limited positive-record diagnostics.

No recoding of 60, no censoring inference, no formal physical-duration predictions.
"""
import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
import sklearn
from scipy.stats import gamma, lognorm
from sklearn.model_selection import LeaveOneGroupOut

from q3_playback_analysis import ROOT, INPUT, COLS, TYPES, CONTEXTS, plt
from q3_count_latency_models import matrix_fit, matrix_apply, optimize
from q3_revised_models import support

BEHAVIORS=['HeadsUp','Approach']
PENALTY=10.
TOL=1e-9  # numerical comparison only, not a claim about measurement precision
STAGE1=ROOT/'results/q3/q3_stage1_20261127T115630Z'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit_duration(d,behavior):
    f=d[behavior+'YesNo'];t=d[behavior+'Latency'];y=d[behavior+'Duration']
    table=pd.DataFrame(dict(source_row_id=d.index+1,exp_id=d.expID,behavior=behavior,
        call_type=d.CallType,context=d.Context,date=d.Date,raw_flag=f,raw_latency_s=t,raw_duration_s=y,
        nominal_remaining_window_s=60-t,raw_latency_plus_duration_s=t+y))
    flags=dict(duration_missing=y.isna(),duration_out_of_range=(y<0)|(y>60),
        invalid_behavior_flag=~f.isin([0,1]),
        flag_duration_conflict=((f==0)&(y>0))|((f==1)&(y<=0)),
        flag_latency_conflict=((f==0)&t.notna())|((f==1)&t.isna()),
        latency_out_of_range=(t<0)|(t>60),
        latency_plus_duration_gt_window=t.notna()&y.notna()&(t+y>60+TOL))
    for key,val in flags.items():table[key]=val
    table['known_conflict']=table[list(flags)].any(axis=1)
    table['duration_equals_60']=y==60
    table['ends_at_nominal_boundary']=(y>0)&t.notna()&((t+y-60).abs()<=TOL)
    table['unresolved_boundary']=table.duration_equals_60|table.ends_at_nominal_boundary
    table['eligible_record']=~table.known_conflict
    table['eligible_positive_record']=table.eligible_record&(y>0)
    table['issue_codes']=['|'.join(k for k in flags if bool(table.loc[i,k])) for i in table.index]
    table['analysis_rule']='duration_record_audit_v1'
    table['duration_encoding_verified']=False
    return table


def summaries(d,audits):
    rows=[]
    for behavior,a in audits.items():
        for version,mask in [('all_original_records',np.ones(len(d),bool)),('exclude_known_conflicts',a.eligible_record.to_numpy())]:
            for typ in ['all']+TYPES:
                for context in ['all']+CONTEXTS:
                    m=mask&((d.CallType==typ).to_numpy() if typ!='all' else True)&((d.Context==context).to_numpy() if context!='all' else True)
                    s=a.loc[m];y=s.raw_duration_s;pos=y[y>0]
                    rows.append(dict(behavior=behavior,version=version,call_type=typ,context=context,n=len(s),
                        duration_observed_n=int(y.notna().sum()),flag_event_n=int((s.raw_flag==1).sum()),
                        positive_n=len(pos),zero_n=int((y==0).sum()),boundary60_n=int(s.duration_equals_60.sum()),
                        conflict_n=int(s.known_conflict.sum()),record_mean=y.mean(),positive_record_mean=pos.mean(),
                        positive_record_median=pos.median(),positive_record_q25=pos.quantile(.25),positive_record_q75=pos.quantile(.75),
                        positive_record_min=pos.min(),positive_record_max=pos.max()))
    return pd.DataFrame(rows)


def record_distribution(family,eta,h):
    shape=np.exp(h)
    return lognorm(shape,scale=np.exp(eta)) if family=='lognormal' else gamma(shape,scale=np.exp(eta)/shape)


def fit_record(train,behavior,family,covariates):
    trans,x=matrix_fit(train,covariates);y=train[behavior+'Duration'].to_numpy(float)
    assert len(y)>1 and np.all(y>0)
    k=x.shape[1]
    def loss(p):
        ll=record_distribution(family,x@p[:k],p[-1]).logpdf(y)
        value=-ll.sum()+PENALTY/2*np.sum(p[1:k]**2)
        return float(value) if np.isfinite(value) else 1e100
    init=np.zeros(k+1)
    if family=='lognormal':
        init[0]=np.log(y).mean();init[-1]=np.log(np.clip(np.log(y).std(),.15,5))
    else:
        init[0]=np.log(y.mean());init[-1]=np.log(np.clip(y.mean()**2/max(y.var(),.01),.15,50))
    alternate=init.copy();alternate[-1]-=.4
    bounds=[(-8,12)]+[(-5,5)]*(k-1)+[(-2.3,2.3) if family=='lognormal' else (-2.3,4.6)]
    result,hits=optimize(loss,[init,alternate],bounds)
    diag=dict(success=bool(result.success),message=str(result.message),objective=float(result.fun),
        params=result.x.tolist(),bound_hit=hits,train_positive_n=len(train),
        absent_positive_train_types=sorted(set(TYPES)-set(train.CallType)))
    return trans,result.x,diag


def predict_record(train,test,behavior,family,covariates,fit):
    if not len(test):
        return pd.DataFrame(columns=['source_row_id','exp_id','actual_record_s','raw_latency_s','mean_record_s',
            'median_record_s','nll','nominal_remaining_window_s','working_prob_exceeds_nominal_window','interpretation'])
    trans,params,_=fit;x=matrix_apply(trans,test,covariates)
    base=record_distribution(family,x@params[:-1],params[-1])
    y=test[behavior+'Duration'].to_numpy(float);nominal=60-test[behavior+'Latency'].to_numpy(float)
    return pd.DataFrame(dict(source_row_id=test.index+1,exp_id=test.expID.to_numpy(),actual_record_s=y,
        raw_latency_s=test[behavior+'Latency'].to_numpy(),mean_record_s=base.mean(),median_record_s=base.ppf(.5),
        nll=-base.logpdf(y),nominal_remaining_window_s=nominal,
        working_prob_exceeds_nominal_window=base.sf(nominal),interpretation='selected_positive_record_working_distribution'))


def scores(oof):
    rows=[]
    for (route,behavior,model),s in oof.groupby(['route','behavior','model']):
        rows.append(dict(route=route,behavior=behavior,model=model,n=len(s),
            mean_record_nll=s.nll.mean(),rmse_record_mean=np.sqrt(np.mean((s.actual_record_s-s.mean_record_s)**2)),
            mae_record_median=np.mean(abs(s.actual_record_s-s.median_record_s)),
            observed_record_mean=s.actual_record_s.mean(),predicted_record_mean=s.mean_record_s.mean(),
            mean_working_prob_exceeds_nominal_window=s.working_prob_exceeds_nominal_window.mean(),
            mean_prediction_exceeds_nominal_fraction=np.mean(s.mean_record_s>s.nominal_remaining_window_s),
            estimand='selected_positive_record_distribution_not_verified_physical_duration'))
    return pd.DataFrame(rows)


def figures(d,audits,oof,figdir):
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    for ax,b in zip(axes,BEHAVIORS):
        a=audits[b];pos=a[a.raw_duration_s>0]
        ax.scatter(pos.raw_latency_s,pos.raw_duration_s,c=np.where(pos.known_conflict,'tab:red','tab:blue'),alpha=.75)
        ax.plot([0,60],[60,0],'k--',linewidth=1,label='Latency + duration = 60')
        ax.set(xlabel='Recorded latency (s)',ylabel='Recorded duration (s)',title=f'{b}: positive records n={len(pos)}',xlim=(-1,61),ylim=(-1,64))
        ax.legend(fontsize=8)
    fig.tight_layout();fig.savefig(figdir/'duration_window_audit.png',dpi=220);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    for ax,b in zip(axes,BEHAVIORS):
        a=audits[b]
        for label,mask in [('All positive records',a.raw_duration_s>0),('After known-conflict exclusion',a.eligible_positive_record)]:
            y=np.sort(a.loc[mask,'raw_duration_s'].to_numpy());ax.step(y,np.arange(1,len(y)+1)/len(y),where='post',label=f'{label} (n={len(y)})')
        ax.set(xlabel='Recorded duration (s)',ylabel='Empirical cumulative proportion',title=b,ylim=(0,1.05));ax.legend(fontsize=8)
    fig.tight_layout();fig.savefig(figdir/'duration_selection_ecdf.png',dpi=220);plt.close(fig)


def run(stage1):
    meta=json.loads((stage1/'metadata.json').read_text());assert sha(INPUT)==meta['input_sha256']
    d=pd.read_csv(INPUT);audits={b:audit_duration(d,b) for b in BEHAVIORS}
    stamp=datetime.now(timezone.utc).strftime('q3_stage5_%Y%m%dT%H%M%SZ')
    out=ROOT/'results/q3'/stamp;out.mkdir(parents=True,exist_ok=False)
    figdir=ROOT/'figures/q3'/stamp;figdir.mkdir(parents=True,exist_ok=False)
    audit=pd.concat(audits.values(),ignore_index=True)
    audit.to_csv(out/'duration_audit.csv',index=False)
    audit[audit.known_conflict|audit.unresolved_boundary].to_csv(out/'duration_issues.csv',index=False)
    summary=summaries(d,audits);summary.to_csv(out/'descriptive_summary.csv',index=False)
    folds=[(np.array(f['train_rows'])-1,np.array(f['test_rows'])-1) for f in meta['reused_outer_folds']]
    routes={'expID':folds,'date':list(LeaveOneGroupOut().split(d,groups=d.Date))}
    oofs=[];diagnostics=[];members=[]
    for b,a in audits.items():
        positive=d.loc[a.eligible_positive_record].copy()
        for i in positive.index:members.append(dict(behavior=b,source_row_id=i+1,exp_id=int(d.expID.iloc[i]),
            population_id=f'duration_{b}_selected_positive_records_v1',boundary_encoding_unresolved=bool(a.unresolved_boundary.iloc[i])))
        for route,splits in routes.items():
            for family in ['lognormal','gamma']:
                for cov in ['type','intercept']:
                    model=f'working_{family}_{cov}'
                    for fold,(tr,te) in enumerate(splits):
                        train=positive.loc[positive.index.isin(tr)];test=positive.loc[positive.index.isin(te)]
                        assert not set(train.expID)&set(test.expID)
                        fit=fit_record(train,b,family,cov)
                        diagnostics.append(dict(route=route,behavior=b,model=model,fold=fold,test_positive_n=len(test),**fit[2]))
                        p=predict_record(train,test,b,family,cov,fit)
                        for key,value in dict(route=route,behavior=b,model=model,fold=fold).items():p[key]=value
                        oofs.append(p)
            for fold,(tr,te) in enumerate(splits):
                train=positive.loc[positive.index.isin(tr)];test=positive.loc[positive.index.isin(te)]
                p=pd.DataFrame(dict(source_row_id=test.index+1,exp_id=test.expID.to_numpy(),actual_record_s=test[b+'Duration'].to_numpy(),
                    raw_latency_s=test[b+'Latency'].to_numpy(),mean_record_s=train[b+'Duration'].mean(),median_record_s=train[b+'Duration'].median(),
                    nll=np.nan,nominal_remaining_window_s=60-test[b+'Latency'].to_numpy(),working_prob_exceeds_nominal_window=np.nan,
                    interpretation='training_positive_record_empirical_reference',route=route,behavior=b,model='empirical_reference',fold=fold))
                oofs.append(p)
        for family in ['lognormal','gamma']:
            for cov in ['type','intercept']:
                fit=fit_record(positive,b,family,cov)
                diagnostics.append(dict(route='full_selected_fit',behavior=b,model=f'working_{family}_{cov}',fold=-1,test_positive_n=0,**fit[2]))
        print('DURATION',b,'selected positive n=',len(positive),flush=True)
    oof=pd.concat([p for p in oofs if len(p)],ignore_index=True);oof.to_csv(out/'duration_oof.csv',index=False)
    validation=scores(oof);validation.to_csv(out/'validation.csv',index=False)
    pd.DataFrame(members).to_csv(out/'analysis_membership.csv',index=False)
    pd.DataFrame(diagnostics).to_json(out/'fit_diagnostics.json',orient='records',indent=2)
    availability=[]
    for b,a in audits.items():
        for typ in TYPES:
            for context in CONTEXTS:
                cell=d[(d.CallType==typ)&(d.Context==context)&a.eligible_record]
                pos=cell[cell[b+'Duration']>0]
                for dist in [50,100,150]:
                    ds='support_unverified' if not len(cell) else 'extrapolation' if dist<cell.Distance.min() or dist>cell.Distance.max() else 'boundary' if dist in [cell.Distance.min(),cell.Distance.max()] else 'interpolation'
                    availability.append(dict(behavior=b,call_type=typ,context=context,distance_m=dist,n_penguins=8,vocal_ncalls_before=0,
                        effective_n=len(cell),positive_n=len(pos),event_n=int(cell[b+'YesNo'].sum()),
                        distance_support=ds,joint_support=support(cell[COLS[2:]].to_numpy(float),np.array([dist,8,0])),
                        conditional_joint_support=support(pos[COLS[2:]].to_numpy(float),np.array([dist,8,0])),
                        extrapolation_reason='outside_selected_joint_support' if support(cell[COLS[2:]].to_numpy(float),np.array([dist,8,0]))=='extrapolation' else '',
                        estimate=np.nan,lower=np.nan,upper=np.nan,observation_window_s=60,
                        estimand='true_response_duration_conditional_arithmetic_mean',analysis_rule='duration_record_audit_v1',
                        model_version='stage5_restricted_diagnostics_v1',availability='not_identified_duration_encoding_unresolved',
                        interval_method='not_generated_encoding_unresolved',bootstrap_success_n=None))
    pd.DataFrame(availability).to_csv(out/'duration_availability.csv',index=False)
    figures(d,audits,oof,figdir)
    files=[INPUT,ROOT/'src/reference_R/Code1_AfricanPenguins_playbacks_analyses.R',ROOT/'problem/2026 APMCM Problem C.pdf',
           ROOT/'problem/attachments/Supplementary3_Modelling_analyses_on_playback_experiments.pdf']
    commit=subprocess.run(['git','-c',f'safe.directory={ROOT.as_posix()}','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True).stdout.strip()
    info=dict(run_id=stamp,input_sha256=sha(INPUT),script_sha256=sha(__file__),git_head=commit,working_tree='uncommitted implementation',
        sources_sha256={str(p.relative_to(ROOT)):sha(p) for p in files},
        helper_sha256={n:sha(ROOT/'src/python'/n) for n in ['q3_count_latency_models.py','q3_revised_models.py','q3_playback_analysis.py']},
        stage1_run=str(stage1.relative_to(ROOT)),versions=dict(numpy=np.__version__,pandas=pd.__version__,scipy=scipy.__version__,sklearn=sklearn.__version__),
        penalty=PENALTY,random_process='none; deterministic grouped splits and optimization',comparison_tolerance=TOL,optimizer='L-BFGS-B maxiter500 ftol1e-10 gtol1e-5, two fixed starts',
        bounds=dict(intercept=[-8,12],slopes=[-5,5],log_sigma=[-2.3,2.3],log_gamma_shape=[-2.3,4.6]),
        folds=[dict(route=r,fold=k,train_rows=(tr+1).tolist(),test_rows=(te+1).tolist()) for r,s in routes.items() for k,(tr,te) in enumerate(s)],
        failed_fits=sum(not x['success'] for x in diagnostics),boundary_fits=sum(bool(x['bound_hit']) for x in diagnostics),
        formal_duration_model_ready=False,duration_encoding_verified=False,stage_scope='restricted_audit_and_working_record_sensitivity_complete',
        reason='No verified boundary encoding or per-record censoring indicator. Selection may be outcome-dependent. No physical-duration model adopted.',
        figure_dir=str(figdir.relative_to(ROOT)),sources_checked=['local problem PDF','local Supplementary3 PDF','original R script',
            'https://ore.eu/article/view/1538/version/2510','https://zenodo.org/records/21376649'],
        published_md5_match=dict(Data02='f936555cb0af178dcb749ec9b51adab5',Code1='311c0036973746a80257d67a5c3a7f2e',Supplementary3='a926bc45af9932567d995b59c5cdafc5'))
    (out/'metadata.json').write_text(json.dumps(info,indent=2),encoding='utf-8')
    (out/'implementation_snapshot.py').write_bytes(Path(__file__).read_bytes())
    print('STAGE5',out)
    print(summary[(summary.call_type=='all')&(summary.context=='all')].to_string(index=False))
    print(validation.to_string(index=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--stage1',type=Path,default=STAGE1);args=parser.parse_args()
    path=args.stage1 if args.stage1.is_absolute() else ROOT/args.stage1
    run(path)
