"""Q3 frozen stages 3/4. New runs only; raw data and earlier implementations immutable.

Penalties and parameter bounds are fixed before evaluation, not selected by OOF scores.
Run from project root: python -B src/python/q3_count_latency_models.py 3
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
from scipy.optimize import minimize
from scipy.special import gammaln, ndtri_exp
from scipy.stats import poisson, nbinom, norm
import sklearn
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.pipeline import make_pipeline

from q3_playback_analysis import ROOT, INPUT, COLS, COMBOS, design, fit_combo, predict_combo
from q3_revised_models import support

STAGE1 = ROOT / 'results/q3/q3_stage1_20261127T115630Z'
COUNT_PENALTY = 1.0  # sum negative log-likelihood + lambda/2 * slope norm squared
TIME_PENALTY = 10.0
WINDOW = 60.0


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def initialize(stage):
    meta = json.loads((STAGE1 / 'metadata.json').read_text())
    assert sha(INPUT) == meta['input_sha256']
    d = pd.read_csv(INPUT)
    d.index = np.arange(len(d))
    stamp = datetime.now(timezone.utc).strftime(f'q3_stage{stage}_%Y%m%dT%H%M%SZ')
    out = ROOT / 'results/q3' / stamp
    out.mkdir(parents=True, exist_ok=False)
    folds = [(np.array(f['train_rows']) - 1, np.array(f['test_rows']) - 1)
             for f in meta['reused_outer_folds']]
    routes = {'expID': folds, 'date': list(LeaveOneGroupOut().split(d, groups=d.Date))}
    return d, out, routes


def metadata(out, stage, routes, diagnostics):
    commit = subprocess.run(['git', '-c', f'safe.directory={ROOT.as_posix()}', 'rev-parse', 'HEAD'],
                            cwd=ROOT, capture_output=True, text=True)
    info = dict(stage=stage, input_sha256=sha(INPUT), script_sha256=sha(__file__),
                helper_sha256={p: sha(ROOT / 'src/python' / p) for p in
                               ['q3_playback_analysis.py', 'q3_revised_models.py']},
                stage1_run=str(STAGE1.relative_to(ROOT)), stage1_metadata_sha256=sha(STAGE1/'metadata.json'),
                git_head=commit.stdout.strip(), working_tree='uncommitted implementation',
                versions=dict(numpy=np.__version__, pandas=pd.__version__, scipy=scipy.__version__, sklearn=sklearn.__version__),
                random_seed=20261127, count_penalty=COUNT_PENALTY, time_penalty=TIME_PENALTY,
                optimization='L-BFGS-B maxiter=500 ftol=1e-10 gtol=1e-5; fixed starts, no outer-score tuning',
                count_bounds=dict(beta=[-12,12],log_alpha=[-8,5]),
                time_bounds=dict(intercept=[-8,12],slopes=[-5,5],log_shape=[-2.3,2.3]),
                time_observation_models=dict(window='population-compatible gate; conditional responder zero atom; truncated positive times',
                    aft='exclude immediate responders from continuous likelihood; remaining no-response rows right-censored at 60; restore training unconditional zero atom'),
                gate='Logistic C=1, same train-only preprocessing; intercept reference uses empirical frequency',
                folds=[dict(route=r, fold=k, train_rows=(tr+1).tolist(), test_rows=(te+1).tolist())
                       for r, splits in routes.items() for k, (tr, te) in enumerate(splits)],
                failed_fits=sum(not x['success'] for x in diagnostics),
                interval_method='not_generated_deferred_to_stage6', bootstrap_success_n=None,
                note='Exploratory validation after prior data inspection. No automatic model selection from outer scores.')
    (out/'metadata.json').write_text(json.dumps(info, indent=2), encoding='utf-8')
    (out/'implementation_snapshot.py').write_bytes(Path(__file__).read_bytes())


def matrix_fit(train, covariates):
    if covariates == 'intercept':
        return None, np.ones((len(train), 1))
    trans = design().fit(train[COLS])
    return trans, matrix_apply(trans, train, covariates)


def matrix_apply(trans, data, covariates):
    if trans is None:
        return np.ones((len(data), 1))
    z = trans.transform(data[COLS])
    if covariates == 'type':
        z = z[:, :3]
    return np.column_stack([np.ones(len(data)), z])


def binary_gate(train, test, target, intercept=False):
    y = np.asarray(target, int)
    if len(np.unique(y)) < 2 or intercept:
        return np.full(len(test), y.mean())
    model = make_pipeline(design(), LogisticRegression(C=1, max_iter=3000, random_state=20261127))
    model.fit(train[COLS], y)
    return model.predict_proba(test[COLS])[:, 1]


def log_nonzero(log_p0):
    return np.log(-np.expm1(log_p0))


def count_logpmf(y, eta, family, log_alpha=0.0):
    """Untruncated NB2 has variance mu + alpha*mu**2; mu is NOT truncated mean."""
    mu = np.exp(eta)
    if family == 'poisson':
        lp = y*eta - mu - gammaln(y+1)
        lp0 = -mu
    else:
        size = np.exp(-log_alpha)
        logp = -np.log1p(mu/size)
        lp0 = size*logp
        lp = gammaln(y+size)-gammaln(size)-gammaln(y+1)+lp0+y*(eta-np.log(size+mu))
    return lp, lp0


def optimize(objective, starts, bounds):
    runs = [minimize(objective, s, method='L-BFGS-B', bounds=bounds,
                     options=dict(maxiter=500, ftol=1e-10, gtol=1e-5)) for s in starts]
    finite = [r for r in runs if np.isfinite(r.fun)]
    if not finite:
        raise RuntimeError('No finite optimizer candidate')
    good = [r for r in finite if r.success]
    result = min(good or finite, key=lambda r: r.fun)
    bound_hit = [i for i, (x, (lo, hi)) in enumerate(zip(result.x, bounds))
                 if min(abs(x-lo), abs(x-hi)) < 1e-4]
    return result, bound_hit


def fit_count(train, family, covariates):
    trans, x = matrix_fit(train, covariates)
    positive = train.VocalNcalls.to_numpy() > 0
    y = train.VocalNcalls.to_numpy()[positive]
    if not len(y):
        raise ValueError('No positive counts in training population')
    xp = x[positive]
    k = x.shape[1]
    def objective(p):
        lp, lp0 = count_logpmf(y, xp@p[:k], family, p[-1] if family == 'nb2' else 0)
        return -(lp-log_nonzero(lp0)).sum()+COUNT_PENALTY/2*np.sum(p[1:k]**2)
    init = np.zeros(k + (family == 'nb2'))
    init[0] = np.log(max(y.mean()-0.5, 0.2))
    starts = [init.copy()]
    if family == 'nb2':
        for a in [-2., 1.]:
            s = init.copy(); s[-1] = a; starts.append(s)
    bounds = [(-12, 12)]*k + ([(-8, 5)] if family == 'nb2' else [])
    result, hits = optimize(objective, starts, bounds)
    diag = dict(success=bool(result.success), message=str(result.message), objective=float(result.fun),
                params=result.x.tolist(), bound_hit=hits, train_n=len(train), positive_n=int(positive.sum()),
                alpha=float(np.exp(result.x[-1])) if family == 'nb2' else 0.0)
    return trans, result.x, diag


def predict_count(train, test, family, covariates, fitted):
    trans, pars, _ = fitted
    x = matrix_apply(trans, test, covariates)
    k = x.shape[1]
    eta = x@pars[:k]
    mu = np.exp(eta)
    _, lp0 = count_logpmf(np.ones(len(test)), eta, family, pars[-1] if family == 'nb2' else 0)
    nz = -np.expm1(lp0)
    q = binary_gate(train, test, train.VocalNcalls.to_numpy() > 0, covariates == 'intercept')
    mean_positive = mu/nz
    base = poisson(mu) if family == 'poisson' else nbinom(np.exp(-pars[-1]), 1/(1+mu*np.exp(pars[-1])))
    target = np.exp(lp0) + np.maximum(0, (0.5-(1-q))/np.maximum(q, 1e-300))*nz
    median = np.where(q <= 0.5, 0, base.ppf(np.minimum(target, 1-1e-14)))
    actual = test.VocalNcalls.to_numpy()
    lp, _ = count_logpmf(actual, eta, family, pars[-1] if family == 'nb2' else 0)
    nll = np.empty(len(test)); pos = actual > 0
    nll[~pos] = -np.log1p(-q[~pos])
    nll[pos] = -np.log(q[pos])-lp[pos]+np.log(nz[pos])
    alpha = np.exp(pars[-1]) if family == 'nb2' else 0
    variance_positive = (mu + (1+alpha)*mu**2)/nz-mean_positive**2
    return pd.DataFrame(dict(source_row_id=test.index+1, exp_id=test.expID.to_numpy(), actual=actual,
        q_positive=q, mean_positive=mean_positive, mean_total=q*mean_positive, median_total=median,
        variance_positive=variance_positive, nll=nll, prob_ge5=q*base.sf(4)/nz, prob_ge10=q*base.sf(9)/nz))


def count_scores(predictions):
    rows=[]
    for (route, model), s in predictions.groupby(['route', 'model']):
        pos=s.actual>0
        rows.append(dict(route=route, model=model, n=len(s), positive_n=int(pos.sum()),
            mean_nll=s.nll.mean(), rmse_mean=np.sqrt(np.mean((s.actual-s.mean_total)**2)),
            mae_median=np.mean(abs(s.actual-s.median_total)), q_brier=np.mean((pos-s.q_positive)**2),
            observed_mean=s.actual.mean(), predicted_mean=s.mean_total.mean(),
            positive_pearson_ratio=np.mean(((s.actual-s.mean_positive)**2/s.variance_positive)[pos]),
            observed_ge5=np.mean(s.actual>=5), predicted_ge5=s.prob_ge5.mean(),
            observed_ge10=np.mean(s.actual>=10), predicted_ge10=s.prob_ge10.mean()))
    return pd.DataFrame(rows)


def representative_grid(population):
    s = pd.read_csv(STAGE1/'representative_support.csv')
    grid = s[s.analysis_population_id == population].reset_index(drop=True)
    cov = pd.DataFrame(dict(CallType=grid.call_type, Context=grid.context, Distance=grid.distance_m,
                            Npenguins=grid.n_penguins, VocalNcallsBefore=grid.vocal_ncalls_before))
    return grid, cov


def stage3():
    d, out, routes=initialize(3)
    assert d.VocalNcalls.notna().all() and (d.VocalNcalls>=0).all()
    assert np.all(d.VocalNcalls == d.VocalNcalls.astype(int))
    records=[];diagnostics=[];grid_records=[]
    for route, folds in routes.items():
        for family in ['poisson','nb2']:
            for covariates in ['full','intercept']:
                model=f'hurdle_{family}_{covariates}'
                for fold,(tr,te) in enumerate(folds):
                    train=d.iloc[tr];test=d.iloc[te]
                    assert not set(train.expID)&set(test.expID)
                    fit=fit_count(train,family,covariates)
                    diagnostics.append(dict(route=route,model=model,fold=fold,**fit[2]))
                    pred=predict_count(train,test,family,covariates,fit)
                    pred['route']=route;pred['model']=model;pred['fold']=fold
                    records.append(pred)
                print('COUNT',route,model,flush=True)
    grid,cov=representative_grid('count_actual_v1')
    for family in ['poisson','nb2']:
        fit=fit_count(d,family,'full')
        diagnostics.append(dict(route='full_fit',model=f'hurdle_{family}_full',fold=-1,**fit[2]))
        cov['VocalNcalls']=0;cov['expID']=-1
        pred=predict_count(d,cov,family,'full',fit)
        for i,row in grid.iterrows():
            cell=d[(d.CallType==row.call_type)&(d.Context==row.context)&(d.VocalNcalls>0)]
            rec=dict(**row.to_dict(),model=f'hurdle_{family}_full',positive_n=len(cell),
                conditional_joint_support=support(cell[COLS[2:]].to_numpy(float),np.array([row.distance_m,8,0])),
                q_positive=pred.q_positive.iloc[i],mean_positive=pred.mean_positive.iloc[i],mean_total=pred.mean_total.iloc[i],
                median_total=pred.median_total.iloc[i],interval_method='deferred_to_stage6',bootstrap_success_n=None,
                event_definition_id='actual_count_positive',analysis_rule='count_actual_v1',model_version='stage3_v1',
                estimand='P(N>0);E[N|N>0];E[N];median(N)',extrapolated_distance=row.distance_support=='extrapolation')
            grid_records.append(rec)
    oof=pd.concat(records,ignore_index=True)
    oof.to_csv(out/'count_oof.csv',index=False)
    scores=count_scores(oof);scores.to_csv(out/'validation.csv',index=False)
    calibration=[]
    for (route,model),s in oof.groupby(['route','model']):
        bins=pd.qcut(s.mean_total,5,duplicates='drop')
        for label,part in s.groupby(bins,observed=True):
            calibration.append(dict(route=route,model=model,bin=str(label),n=len(part),
                predicted_mean=part.mean_total.mean(),observed_mean=part.actual.mean(),
                predicted_positive=part.q_positive.mean(),observed_positive=np.mean(part.actual>0)))
    pd.DataFrame(calibration).to_csv(out/'calibration.csv',index=False)
    pd.DataFrame(grid_records).to_csv(out/'count_predictions.csv',index=False)
    pd.DataFrame(diagnostics).to_json(out/'fit_diagnostics.json',orient='records',indent=2)
    metadata(out,3,routes,diagnostics)
    print('STAGE3',out);print(scores.to_string(index=False))


def time_logs(t, eta, log_shape, family):
    """Positive-time log density/CDF/survival, in seconds; never called with zero."""
    t=np.asarray(t,float)
    assert np.all(t>0)
    logt=np.log(t)
    shape=np.exp(log_shape)
    if family=='lognormal':
        z=(logt-eta)/shape
        return norm.logpdf(z)-np.log(shape)-logt, norm.logcdf(z), norm.logsf(z)
    logz=shape*(logt-eta)
    z=np.exp(np.minimum(logz,700))
    # log F ~ log z in the very small tail; avoids underflow, not a data adjustment.
    lc=np.where(logz < -35, logz, np.log(-np.expm1(-z)))
    return log_shape-logt+logz-z, lc, -z


def time_quantile(u, eta, log_shape, family):
    """Quantile of positive T conditional on T<=60, via log-CDF inversion."""
    _,lc,_=time_logs(WINDOW,eta,log_shape,family)
    lu=np.log(np.asarray(u))+lc
    if family=='lognormal':
        return np.exp(eta+np.exp(log_shape)*ndtri_exp(lu))
    logneg=np.where(lu < -35,lu,np.log(-np.log1p(-np.exp(lu))))
    return np.exp(eta+logneg/np.exp(log_shape))


def positive_time_mean(eta, log_shape, family):
    # E[T | 0<T<=60] = 60 - integral_0^60 F(t)/F(60) dt; bounded quadrature.
    nodes,weights=np.polynomial.legendre.leggauss(96)
    t=(nodes+1)*WINDOW/2
    _,lc,_=time_logs(WINDOW,eta,log_shape,family)
    _,lct,_=time_logs(t[:,None],eta[None,:],log_shape,family)
    return WINDOW-WINDOW/2*np.sum(weights[:,None]*np.exp(lct-lc[None,:]),axis=0)


def fit_time(train, behavior, family, covariates, observation):
    trans,x=matrix_fit(train,covariates)
    event=train['_event'].to_numpy(bool)
    time=train[behavior+'Latency'].to_numpy(float)
    pos=event&(time>0);zero=event&(time==0);none=~event
    assert np.all(np.isfinite(time[event])) and np.all(time[event]>=0) and np.all(time[event]<=WINDOW)
    if not pos.any():
        raise ValueError('No positive latency events in training population')
    k=x.shape[1]
    def objective(p):
        eta=x@p[:k]
        lp,_,_=time_logs(time[pos],eta[pos],p[-1],family)
        if observation=='window':
            _,lc,_=time_logs(WINDOW,eta[pos],p[-1],family)
            ll=(lp-lc).sum()
        else:
            # AFT population is explicitly non-immediate: positive events + no response.
            _,_,ls=time_logs(WINDOW,eta[none],p[-1],family)
            ll=lp.sum()+ls.sum()
        value=-ll+TIME_PENALTY/2*np.sum(p[1:k]**2)
        return value if np.isfinite(value) else 1e100
    init=np.zeros(k+1);init[0]=np.log(np.median(time[pos]))
    init[-1]=0 if family=='lognormal' else np.log(1.2)
    alternate=init.copy();alternate[0]+=1;alternate[-1]-=.4
    bounds=[(-8,12)]+[(-5,5)]*(k-1)+[(-2.3,2.3)]
    result,hits=optimize(objective,[init,alternate],bounds)
    diag=dict(success=bool(result.success),message=str(result.message),objective=float(result.fun),
        params=result.x.tolist(),bound_hit=hits,train_n=len(train),event_n=int(event.sum()),
        zero_n=int(zero.sum()),positive_n=int(pos.sum()),censored_n=int(none.sum()) if observation=='aft' else 0,
        positive_aft_population_n=int((pos|none).sum()) if observation=='aft' else None,
        unobserved_positive_types=sorted(set(['control','flat','mod','tv'])-set(train.loc[pos,'CallType'])))
    return trans,result.x,diag


def event_probability(train,test,behavior,version,covariates):
    if covariates=='intercept':
        return np.full(len(test),train['_event'].mean())
    if behavior=='HeadsUp' or version=='original_flags':
        p=predict_combo(fit_combo(train,1),test)
        j=['HeadsUp','Vocal','Approach'].index(behavior)
        return p[:,[i for i,c in enumerate(COMBOS) if c[j]=='1']].sum(axis=1)
    # Excluded-population V/A or changed event definition: refit its own gate.
    return binary_gate(train,test,train['_event'])


def predict_time(train,test,behavior,family,covariates,observation,version,fitted):
    trans,params,diag=fitted
    x=matrix_apply(trans,test,covariates);eta=x@params[:-1];h=params[-1]
    event=train['_event'].to_numpy(bool);t=train[behavior+'Latency'].to_numpy(float)
    zero=event&(t==0)
    _,lc60,ls60=time_logs(WINDOW,eta,h,family)
    if observation=='window':
        p=event_probability(train,test,behavior,version,covariates)
        pi0=zero.sum()/event.sum()
        mass0=p*pi0;masspos=p*(1-pi0);massnone=1-p
    else:
        # Separate unconditional recorded-zero atom. AFT conditions on not immediate,
        # fits positive times and administrative censoring, then restores the atom.
        r=zero.mean()
        mass0=np.full(len(test),r)
        masspos=(1-r)*np.exp(lc60);massnone=(1-r)*np.exp(ls60)
        p=mass0+masspos
    assert np.allclose(mass0+masspos+massnone,1)
    actual_event=test['_event'].to_numpy(bool)
    actual_time=test[behavior+'Latency'].to_numpy(float)
    pos=actual_event&(actual_time>0);zerotest=actual_event&(actual_time==0);none=~actual_event
    nll=np.empty(len(test))
    nll[none]=-np.log(massnone[none])
    nll[zerotest]=-np.log(mass0[zerotest])
    lp,_,_=time_logs(actual_time[pos],eta[pos],h,family)
    nll[pos]=-np.log(masspos[pos])-lp+lc60[pos]
    # Quantile of conditional responders, accounting for the atom at recorded zero.
    u=(.5*p-mass0)/np.maximum(masspos,1e-300)
    median=np.zeros(len(test));positive_median=u>0
    median[positive_median]=time_quantile(u[positive_median],eta[positive_median],h,family)
    out=pd.DataFrame(dict(source_row_id=test.index+1,exp_id=test.expID.to_numpy(),
        actual_event=actual_event.astype(int),actual_latency_s=actual_time,p_response=p,
        mass_no_response=massnone,mass_recorded_zero=mass0,mass_positive=masspos,nll=nll,
        positive_median_s=time_quantile(np.full(len(test),.5),eta,h,family),
        conditional_median_s=median,positive_mean_s=positive_time_mean(eta,h,family)))
    out['conditional_mean_s']=out.positive_mean_s*masspos/np.maximum(p,1e-300)
    out['pi_zero_given_response']=mass0/np.maximum(p,1e-300)
    for cutoff in [1,5,10,30,60]:
        _,lct,_=time_logs(cutoff,eta,h,family)
        out[f'cdf_{cutoff}s']=mass0+masspos*np.exp(lct-lc60)
    return out


def latency_population(d,behavior,version):
    conflict=(d[behavior+'YesNo']==0)&d[behavior+'Latency'].notna()
    sub=d.loc[~conflict].copy() if version=='exclude_conflicts' else d.copy()
    sub['_event']=sub[behavior+'YesNo'].astype(int)
    if version=='time_evidence':
        sub['_event']=((sub['_event']==1)|sub[behavior+'Latency'].notna()).astype(int)
    return sub


def latency_scores(oof,d):
    rows=[]
    for (route,behavior,version,model),s in oof.groupby(['route','behavior','version','model']):
        common_ids=latency_population(d,behavior,'exclude_conflicts').index+1
        for scope,part in [('version_population',s),('common_evaluable',s[s.source_row_id.isin(common_ids)])]:
            event=part.actual_event==1
            row=dict(route=route,behavior=behavior,version=version,model=model,evaluation_scope=scope,
                n=len(part),event_n=int(event.sum()),zero_n=int((event&(part.actual_latency_s==0)).sum()),
                mean_joint_nll=part.nll.mean(),response_brier=np.mean((part.actual_event-part.p_response)**2),
                observed_response=part.actual_event.mean(),predicted_response=part.p_response.mean(),
                conditional_median_mae=np.mean(abs(part.loc[event,'actual_latency_s']-part.loc[event,'conditional_median_s'])))
            for cutoff in [1,5,10,30,60]:
                actual=(event&(part.actual_latency_s<=cutoff)).astype(int)
                row[f'brier_{cutoff}s']=np.mean((actual-part[f'cdf_{cutoff}s'])**2)
            rows.append(row)
    return pd.DataFrame(rows)


def stage4():
    d,out,routes=initialize(4)
    records=[];diagnostics=[];grid_records=[];populations=[]
    for behavior in ['HeadsUp','Vocal','Approach']:
        versions=['exclude_conflicts'] if behavior=='HeadsUp' else ['exclude_conflicts','original_flags','time_evidence']
        for version in versions:
            pop=latency_population(d,behavior,version)
            populations.append(dict(behavior=behavior,version=version,n=len(pop),event_n=int(pop['_event'].sum()),
                zero_n=int(((pop['_event']==1)&(pop[behavior+'Latency']==0)).sum()),source_row_ids=(pop.index+1).tolist(),
                window_probability_interface='original_combo_marginal' if behavior=='HeadsUp' or version=='original_flags' else 'separately_fitted_population_gate',
                aft_probability_interface='1 - (1-unconditional_zero_atom)*S(60 | non-immediate); not shared with window gate',
                aft_conditioning='non-immediate population: positive events and no response; zero atom restored separately'))
            cases=[(obs,fam,cov) for obs in ['window','aft'] for fam in ['lognormal','weibull']
                   for cov in (['type','full','intercept'] if obs=='window' and version=='exclude_conflicts' else ['type'])]
            for route,folds in routes.items():
                if version!='exclude_conflicts' and route!='expID':continue
                for observation,family,covariates in cases:
                    model=f'{observation}_{family}_{covariates}'
                    for fold,(tr,te) in enumerate(folds):
                        train=pop.loc[pop.index.isin(tr)];test=pop.loc[pop.index.isin(te)]
                        assert not set(train.expID)&set(test.expID)
                        fit=fit_time(train,behavior,family,covariates,observation)
                        diagnostics.append(dict(route=route,behavior=behavior,version=version,model=model,fold=fold,**fit[2]))
                        pred=predict_time(train,test,behavior,family,covariates,observation,version,fit)
                        for key,value in dict(route=route,behavior=behavior,version=version,model=model,fold=fold).items():pred[key]=value
                        records.append(pred)
                    print('LATENCY',behavior,version,route,model,flush=True)
            # Representative outputs include conflict sensitivities, with population-specific support.
            population_id=f'latency_{behavior}_v1' if version=='exclude_conflicts' else 'combo_all_v1'
            grid,cov=representative_grid(population_id)
            cov['expID']=-1;cov['_event']=0;cov[behavior+'Latency']=np.nan
            for observation,family,covariates in cases:
                model=f'{observation}_{family}_{covariates}'
                fit=fit_time(pop,behavior,family,covariates,observation)
                diagnostics.append(dict(route='full_fit',behavior=behavior,version=version,model=model,fold=-1,**fit[2]))
                pred=predict_time(pop,cov,behavior,family,covariates,observation,version,fit)
                for i,row in grid.iterrows():
                    cell=pop[(pop.CallType==row.call_type)&(pop.Context==row.context)]
                    positive=cell[(cell['_event']==1)&(cell[behavior+'Latency']>0)]
                    rec=row.to_dict()
                    rec.update(analysis_population_id=f'latency_{behavior}_{version}_v1',event_n=int(cell['_event'].sum()),
                        behavior=behavior,version=version,model=model,positive_n=len(positive),
                        conditional_joint_support=support(positive[COLS[2:]].to_numpy(float),np.array([row.distance_m,8,0])),
                        positive_time_evidence='observed_in_cell' if len(positive) else 'none_in_cell_model_borrows_other_cells',
                        event_definition_id='flags_or_recorded_time' if version=='time_evidence' else 'original_behavior_flag',
                        analysis_rule=f'latency_{behavior}_{version}_v1',model_version='stage4_v1',
                        estimand='P(T<=60);recorded_zero_mass;T|response conditional median/arithmetic mean;CDF(1,5,10,30,60)',
                        observation_window_s=60,interval_method='deferred_to_stage6',bootstrap_success_n=None,
                        extrapolated_distance=row.distance_support=='extrapolation')
                    for col in ['p_response','mass_no_response','mass_recorded_zero','mass_positive','positive_median_s',
                                'conditional_median_s','positive_mean_s','conditional_mean_s','pi_zero_given_response']+[f'cdf_{t}s' for t in [1,5,10,30,60]]:
                        rec[col]=pred[col].iloc[i]
                    grid_records.append(rec)
    oof=pd.concat(records,ignore_index=True)
    oof.to_csv(out/'latency_oof.csv',index=False)
    score=latency_scores(oof,d);score.to_csv(out/'validation.csv',index=False)
    pd.DataFrame(grid_records).to_csv(out/'latency_predictions.csv',index=False)
    pd.DataFrame(diagnostics).to_json(out/'fit_diagnostics.json',orient='records',indent=2)
    (out/'population_definitions.json').write_text(json.dumps(populations,indent=2),encoding='utf-8')
    calibration=[]
    for (route,behavior,version,model),s in oof.groupby(['route','behavior','version','model']):
        for cutoff in [1,5,10,30,60]:
            prob=s[f'cdf_{cutoff}s'];actual=((s.actual_event==1)&(s.actual_latency_s<=cutoff)).astype(int)
            bins=np.minimum((prob.to_numpy()*5).astype(int),4)
            for b in range(5):
                mask=bins==b
                calibration.append(dict(route=route,behavior=behavior,version=version,model=model,time_s=cutoff,
                    bin_left=b/5,n=int(mask.sum()),predicted=prob[mask].mean(),observed=actual[mask].mean()))
    pd.DataFrame(calibration).to_csv(out/'calibration.csv',index=False)
    metadata(out,4,routes,diagnostics)
    print('STAGE4',out)
    print(score[(score.route=='expID')&(score.version=='exclude_conflicts')&
                (score.evaluation_scope=='version_population')].to_string(index=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['3','4'])
    args=parser.parse_args()
    if args.stage=='3':stage3()
    else:stage4()
