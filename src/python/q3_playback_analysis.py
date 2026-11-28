"""Q3 reproducible exploratory baseline; grouped validation/bootstrap, no Q1 relabeling."""
import hashlib
import json
import os
import platform
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault('MPLCONFIGDIR',str(Path(tempfile.gettempdir())/'apmcm_q3'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy
from scipy.stats import binomtest
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import log_loss, mean_absolute_error
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

ROOT=Path(__file__).resolve().parents[2]
INPUT=ROOT/'data/raw/playbacks/Data02_AfricanPenguins_playbacks_data.csv'
TYPES=['control','flat','mod','tv'];CONTEXTS=['after','commuting','searching']
BEHAVIORS=['HeadsUp','Vocal','Approach'];FLAGS=[s+'YesNo' for s in BEHAVIORS]
COMBOS=[f'{i:03b}' for i in range(8)] # actual string order HVA
COLS=['CallType','Context','Distance','Npenguins','VocalNcallsBefore']
SEED=20261127; BOOTSTRAPS=200


def design():
    return ColumnTransformer([('cats',OneHotEncoder(categories=[TYPES,CONTEXTS],drop='first',handle_unknown='error',sparse_output=False),COLS[:2]),
                              ('numeric',StandardScaler(),COLS[2:])])


def combo(d):
    return d[FLAGS].astype(int).astype(str).agg(''.join,axis=1)


def fit_combo(d,C=1):
    model=make_pipeline(design(),LogisticRegression(C=C,solver='lbfgs',max_iter=3000,random_state=SEED))
    model.fit(d[COLS],combo(d));return model


def predict_combo(model,d):
    p=np.zeros((len(d),8));p[:,[COMBOS.index(c) for c in model[-1].classes_]]=model.predict_proba(d[COLS])
    assert np.allclose(p.sum(1),1);return p


def behavior_probs(p):
    return np.column_stack([p[:,[i for i,c in enumerate(COMBOS) if c[j]=='1']].sum(1) for j in range(3)])


def conditional(d,g):
    """Within-window observed conditional geometric means; not population survival times."""
    outputs=[]
    for j,b in enumerate(BEHAVIORS):
        for target in [b+'Latency', 'VocalNcalls' if b=='Vocal' else b+'Duration']:
            positive=d[(d[b+'YesNo']==1)&(d[target]>0)].copy()
            if len(positive)<2:raise ValueError('Insufficient conditional data: '+target)
            # Penalized lognormal regression; zero-latency atom handled separately.
            model=make_pipeline(design(),Ridge(alpha=10))
            model.fit(positive[COLS],np.log(positive[target]))
            v=np.exp(model.predict(g[COLS]))
            upper=60 if target!='VocalNcalls' else np.inf
            v=np.minimum(v,upper)
            for k,row in g.iterrows():
                cell=d[(d.CallType==row.CallType)&(d.Context==row.Context)]
                supported=bool((cell[b+'YesNo']==1).any())
                event=d[d[b+'YesNo']==1]
                pzero=float((event[target]==0).mean()) if target.endswith('Latency') else 0.0
                outputs.append(dict(grid_row=k,behavior=b,target=target,
                    conditional_positive_geometric_mean=float(v[k]) if supported else np.nan,
                    immediate_fraction_among_responders=pzero,
                    status='conditional_observed_response' if supported else 'no_observed_response',
                    n_positive_fit=len(positive)))
    return pd.DataFrame(outputs)


def main():
    d=pd.read_csv(INPUT);original=d.copy(deep=True)
    assert d.shape==(278,40) and not d.duplicated().any()
    assert (d.groupby('expID').size()==2).all() and (d.groupby('expID').Type.nunique()==2).all()
    assert set(d.CallType)==set(TYPES) and set(d.Context)==set(CONTEXTS)
    assert (d.ResponseYesNo==d[FLAGS].max(axis=1)).all()
    run_id=datetime.now(timezone.utc).strftime('q3_%Y%m%dT%H%M%SZ')
    out=ROOT/'results/q3'/run_id;out.mkdir(parents=True,exist_ok=False)
    issues=[]
    for i,row in d.iterrows():
        for b in BEHAVIORS:
            t=b+'Latency';v=row[t]
            if row[b+'YesNo']==0 and pd.notna(v):issues.append(dict(source_row_id=i+1,exp_id=row.expID,field=t,issue='latency_present_but_flag_zero',value=v))
            if b!='Vocal' and row[b+'YesNo']==1 and pd.notna(v) and v+row[b+'Duration']>60:
                issues.append(dict(source_row_id=i+1,exp_id=row.expID,field=b+'Duration',issue='latency_plus_duration_over_window',value=row[b+'Duration']))
    pd.DataFrame(issues).to_csv(out/'audit_issues.csv',index=False)
    cleaned=d.copy();cleaned.insert(0,'source_row_id',np.arange(1,len(d)+1));cleaned['combo_hva']=combo(d)
    cleaned['analysis_rule']='original_binary_flags_v1';cleaned.to_csv(out/'playbacks_clean.csv',index=False)
    pd.crosstab(d.CallType,d.Context).to_csv(out/'sample_sizes.csv')
    rate=d.groupby('Type')[['ResponseYesNo',*FLAGS]].agg(['sum','mean','count']);rate.to_csv(out/'observed_response_rates.csv')
    pd.crosstab(combo(d),d.Type).reindex(COMBOS,fill_value=0).to_csv(out/'observed_combinations.csv')
    paired=d.pivot(index='expID',columns='Type',values='ResponseYesNo')
    call_only=int(((paired['call']==1)&(paired.control==0)).sum());control_only=int(((paired['call']==0)&(paired.control==1)).sum())
    paired_p=binomtest(call_only,call_only+control_only,.5).pvalue
    g=pd.DataFrame([dict(CallType=t,Context=c,Distance=dist,Npenguins=8,VocalNcallsBefore=float(d.VocalNcallsBefore.median()))
                    for t in TYPES for c in CONTEXTS for dist in [50,100,150]])
    model=fit_combo(d);p=predict_combo(model,g);pbehavior=behavior_probs(p)
    cond=conditional(d,g)
    ids=d.expID.unique();rng=np.random.default_rng(SEED);boot=[];boot_cond=[]
    for b in range(BOOTSTRAPS):
        sampled=rng.choice(ids,len(ids),replace=True)
        sample=pd.concat([d[d.expID==i] for i in sampled],ignore_index=True)
        boot.append(predict_combo(fit_combo(sample),g))
        boot_cond.append(conditional(sample,g).conditional_positive_geometric_mean.to_numpy())
        if b%50==0:print('BOOTSTRAP',b,flush=True)
    boot=np.array(boot);lo,hi=np.quantile(boot,[.025,.975],axis=0)
    np.savez_compressed(out/'bootstrap_predictions.npz',combination=boot,conditional_positive=np.array(boot_cond))
    bp=np.array([behavior_probs(v) for v in boot]);blo,bhi=np.quantile(bp,[.025,.975],axis=0)
    # Unsupported observed cells remain missing; bootstrap supports may vary.
    bc=np.array(boot_cond)
    clo=[];chi=[]
    for k in range(bc.shape[1]):
        valid=bc[:,k][np.isfinite(bc[:,k])]
        clo.append(float(np.quantile(valid,.025)) if len(valid) else np.nan)
        chi.append(float(np.quantile(valid,.975)) if len(valid) else np.nan)
    rows=[]
    for k,row in g.iterrows():
        cell=d[(d.CallType==row.CallType)&(d.Context==row.Context)]
        for j,c in enumerate(COMBOS):rows.append(dict(call_type=row.CallType,context=row.Context,distance_m=row.Distance,
            n_penguins=8,combo=c,probability=p[k,j],lower=lo[k,j],upper=hi[k,j],
            extrapolated_distance=bool(row.Distance<cell.Distance.min() or row.Distance>cell.Distance.max()),run_id=run_id))
    pd.DataFrame(rows).to_csv(out/'combination_predictions.csv',index=False)
    cond['lower']=clo;cond['upper']=chi
    cond['bootstrap_valid_n']=np.isfinite(bc).sum(axis=0)
    details=[]
    for _,r in cond.iterrows():
        k=int(r.grid_row);j=BEHAVIORS.index(r.behavior);row=g.iloc[k]
        details.append(dict(call_type=row.CallType,context=row.Context,distance_m=row.Distance,n_penguins=8,
            behavior=r.behavior,outcome=r.target,response_probability=pbehavior[k,j],response_lower=blo[k,j],response_upper=bhi[k,j],
            conditional_positive_geometric_mean=r.conditional_positive_geometric_mean,
            lower=r.lower if r.status!='no_observed_response' else np.nan,upper=r.upper if r.status!='no_observed_response' else np.nan,
            immediate_fraction_among_responders=r.immediate_fraction_among_responders,status=r.status,
            unit='count' if r.target=='VocalNcalls' else 's',n_positive_fit=r.n_positive_fit,
            bootstrap_valid_n=r.bootstrap_valid_n,run_id=run_id))
    pd.DataFrame(details).to_csv(out/'latency_intensity_predictions.csv',index=False)
    # Standardized counterfactual differences conditional on the observed covariate distribution.
    contrasts=[]
    for t in TYPES[1:]:
        a=d.copy();a['CallType']=t;z=d.copy();z['CallType']='control'
        pa=predict_combo(model,a);pz=predict_combo(model,z)
        for j,c in enumerate(COMBOS):contrasts.append(dict(call_type=t,combo=c,standardized_probability_difference=float((pa-pz)[:,j].mean())))
    pd.DataFrame(contrasts).to_csv(out/'call_control_contrasts.csv',index=False)
    paired_contrasts=[]
    for k,row in g.iterrows():
        if row.CallType=='control':continue
        control_index=g.index[(g.CallType=='control')&(g.Context==row.Context)&(g.Distance==row.Distance)][0]
        difference=boot[:,k,:]-boot[:,control_index,:]
        dl,du=np.quantile(difference,[.025,.975],axis=0)
        for j,c in enumerate(COMBOS):
            paired_contrasts.append(dict(call_type=row.CallType,context=row.Context,distance_m=row.Distance,
                n_penguins=8,combo=c,probability_difference=p[k,j]-p[control_index,j],lower=dl[j],upper=du[j]))
    pd.DataFrame(paired_contrasts).to_csv(out/'representative_call_control_contrasts.csv',index=False)
    # Group CV with a train-only smoothed category-frequency reference.
    oof=np.zeros((len(d),8));base=np.zeros_like(oof);folds=[];cond_errors=[]
    for f,(tr,te) in enumerate(GroupKFold(5).split(d,groups=d.expID)):
        assert not set(d.expID.iloc[tr])&set(d.expID.iloc[te])
        oof[te]=predict_combo(fit_combo(d.iloc[tr]),d.iloc[te]);freq=combo(d.iloc[tr]).value_counts().reindex(COMBOS,fill_value=0).to_numpy()+1
        base[te]=freq/freq.sum();folds.append(dict(fold=f,train_rows=(tr+1).tolist(),test_rows=(te+1).tolist()))
        for b in BEHAVIORS:
            for target in [b+'Latency','VocalNcalls' if b=='Vocal' else b+'Duration']:
                train=d.iloc[tr];test=d.iloc[te]
                train=train[(train[b+'YesNo']==1)&(train[target]>0)]
                test=test[(test[b+'YesNo']==1)&(test[target]>0)]
                if len(train)>1 and len(test):
                    m=make_pipeline(design(),Ridge(alpha=10)).fit(train[COLS],np.log(train[target]))
                    v=np.exp(m.predict(test[COLS]));ref=np.repeat(np.exp(np.log(train[target]).mean()),len(test))
                    for actual,pred,reference in zip(test[target],v,ref):cond_errors.append(dict(target=target,actual=actual,predicted=pred,reference=reference))
    y=combo(d);yp=d.ResponseYesNo.to_numpy();pr=1-oof[:,0]
    validation=dict(combo_logloss=log_loss(y,oof,labels=COMBOS),reference_logloss=log_loss(y,base,labels=COMBOS),
                    response_brier=float(np.mean((yp-pr)**2)),reference_brier=float(np.mean((yp-(1-base[:,0]))**2)))
    pd.DataFrame(dict(source_row_id=np.arange(1,len(d)+1),exp_id=d.expID,combo=y,response_probability=pr)).to_csv(out/'oof_response.csv',index=False)
    ce=pd.DataFrame(cond_errors);ce.to_csv(out/'conditional_validation.csv',index=False)
    # Original flags vs conservative inclusive-evidence sensitivity; never overwrite raw values.
    inclusive=d.copy()
    inclusive['VocalYesNo']=((d.VocalYesNo==1)|(d.VocalNcalls>0)).astype(int)
    inclusive['ApproachYesNo']=((d.ApproachYesNo==1)|d.ApproachLatency.notna()).astype(int)
    sensitivity=[]
    for label,data,C in [('original_C025',d,.25),('original_C4',d,4),('inclusive_evidence',inclusive,1)]:
        pp=predict_combo(fit_combo(data,C),g)
        alt=conditional(data,g).conditional_positive_geometric_mean.to_numpy()
        ref=cond.conditional_positive_geometric_mean.to_numpy();valid=np.isfinite(alt)&np.isfinite(ref)
        sensitivity.append(dict(scenario=label,max_abs_any_response_change=float(np.max(np.abs(pp[:,0]-p[:,0]))),
                                mean_abs_combo_change=float(np.mean(np.abs(pp-p))),
                                max_relative_conditional_change=float(np.max(np.abs(alt[valid]/ref[valid]-1)))))
    pd.DataFrame(sensitivity).to_csv(out/'sensitivity.csv',index=False)
    # Duration/intensity vs latency remain different outcomes.
    fig,ax=plt.subplots(figsize=(8,4),layout='constrained')
    freq=pd.crosstab(combo(d),d.Type,normalize='columns').reindex(COMBOS,fill_value=0)
    xx=np.arange(8);ax.bar(xx-.18,freq['call'],.36,label='Natural call');ax.bar(xx+.18,freq['control'],.36,label='Control')
    ax.set_xticks(xx,COMBOS);ax.set_xlabel('Response combination (HVA)');ax.set_ylabel('Observed proportion');ax.legend()
    fig.savefig(out/'observed_combinations.png',dpi=180);plt.close(fig)
    fig,ax=plt.subplots(figsize=(8,4),layout='constrained')
    for t in TYPES:
        mask=(g.CallType==t)&(g.Context=='searching')
        ax.plot(g.loc[mask,'Distance'],1-p[mask,0],marker='o',label=t)
    ax.set_xlabel('Distance (m)');ax.set_ylabel('Any response probability within 60 s');ax.legend();ax.set_title('Searching context; N=8; fixed baseline vocal count')
    fig.savefig(out/'response_predictions.png',dpi=180);plt.close(fig)
    assert d.equals(original)
    head=subprocess.check_output(['git','-c','safe.directory='+str(ROOT),'rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    meta=dict(run_id=run_id,input_sha256=hashlib.sha256(INPUT.read_bytes()).hexdigest(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        git_head=head,seed=SEED,bootstrap_replicates=BOOTSTRAPS,bootstrap_unit='expID; both records sampled together',folds=folds,
        validation=validation,sensitivity=sensitivity,paired=dict(call_only=call_only,control_only=control_only,p_value=paired_p),
        model='L2 multinomial logistic C=1; CallType + Context + standardized Distance, Npenguins, VocalNcallsBefore; additive main effects',
        conditional='Ridge alpha=10 on log positive observed outcomes; predicted geometric mean; duration clipped at 60. No unobserved uncensored intensity inference.',
        latency='No response separate; zero HeadUp latency empirical atom among responders, positive-time log regression. Not survival/AFT, no 60 s substituted as observed latency.',
        source='https://ore.eu/article/view/1538/version/2510; 60 s window, group observation, seconds confirmed',
        limitations='No experiment random effects or track random effects; group CV/bootstrap handle dependence for evaluation/intervals only. Bootstrap percentile 95% intervals conditional on fixed model; not causal. 23 approach events; sparse combinations; model may predict nonzero unsupported outcomes.',
        fitted_combo=dict(classes=model[-1].classes_.tolist(),coefficients=model[-1].coef_.tolist(),intercepts=model[-1].intercept_.tolist(),
                          feature_names=model[0].get_feature_names_out().tolist(),numeric_mean=model[0].named_transformers_['numeric'].mean_.tolist(),
                          numeric_scale=model[0].named_transformers_['numeric'].scale_.tolist()),
        versions=dict(python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__,scipy=scipy.__version__,sklearn=sklearn.__version__))
    (out/'metadata.json').write_text(json.dumps(meta,indent=2,ensure_ascii=False),encoding='utf-8')
    print('OUTPUT',out);print('VALIDATION',validation);print('PAIRED',meta['paired']);print('SENSITIVITY',sensitivity)
    print('RATES',rate.to_string());print('CONDITIONAL_MAE',ce.groupby('target')[['actual','predicted','reference']].apply(lambda a:pd.Series({'mae':mean_absolute_error(a.actual,a.predicted),'reference_mae':mean_absolute_error(a.actual,a.reference)})).to_string())


if __name__=='__main__':main()
