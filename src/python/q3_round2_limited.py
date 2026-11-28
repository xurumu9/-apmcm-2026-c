"""R2-5 predeclared NB2 penalty-only nested grouped sensitivity."""
import json
import hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from sklearn.model_selection import GroupKFold
from threadpoolctl import threadpool_limits
from q3_playback_analysis import ROOT,INPUT
from q3_count_latency_models import matrix_fit,count_logpmf,log_nonzero,predict_count,count_scores
from q3_round2_pattern import FOUNDATION

OUT=FOUNDATION.parent/'R2_5'
LAMBDAS=[.25,1.,4.]


def fit(train,lam):
    trans,x=matrix_fit(train,'full');yes=train.VocalNcalls.to_numpy()>0;y=train.VocalNcalls.to_numpy()[yes];xp=x[yes];k=x.shape[1]
    def objective(p):
        lp,lp0=count_logpmf(y,xp@p[:k],'nb2',p[-1]);return -(lp-log_nonzero(lp0)).sum()+lam/2*np.sum(p[1:k]**2)
    init=np.zeros(k+1);init[0]=np.log(max(y.mean()-.5,.2));starts=[]
    for loga in [0.,-2.,1.]:
        v=init.copy();v[-1]=loga;starts.append(v)
    bounds=[(-12,12)]*k+[(-8,5)]
    runs=[minimize(objective,s,method='L-BFGS-B',bounds=bounds,options=dict(maxiter=500,ftol=1e-10,gtol=1e-5)) for s in starts]
    valid=[r for r in runs if r.success and np.isfinite(r.fun)]
    if not valid:raise RuntimeError('No converged finite initialisation')
    best=min(valid,key=lambda r:r.fun)
    diag=dict(success=True,lambda_definition='negative_total_positive_loglikelihood_plus_lambda_over2_slope_squared_no_intercept_or_alpha_penalty',
        lambda_value=lam,train_n=len(train),positive_n=int(yes.sum()),alpha=float(np.exp(best.x[-1])),objective=float(best.fun),
        bound_hit=[j for j,(v,(lo,hi)) in enumerate(zip(best.x,bounds)) if min(abs(v-lo),abs(v-hi))<1e-4],
        starts=[dict(log_alpha_initial=s[-1],success=bool(r.success),objective=float(r.fun),alpha=float(np.exp(r.x[-1])),message=str(r.message)) for s,r in zip(starts,runs)])
    return trans,best.x,diag


def run():
    OUT.mkdir(parents=True,exist_ok=False);d=pd.read_csv(INPUT)
    meta=json.loads((ROOT/'results/q3/q3_stage1_20261127T115630Z/metadata.json').read_text());records=[];choices=[];diagnostics=[]
    with threadpool_limits(limits=1):
        for f in meta['reused_outer_folds']:
            train=d.iloc[np.array(f['train_rows'])-1];test=d.iloc[np.array(f['test_rows'])-1];fold=f['fold'];inner_scores={}
            for lam in LAMBDAS:
                losses=[]
                for inner,(tr,va) in enumerate(GroupKFold(3).split(train,groups=train.expID)):
                    fitted=fit(train.iloc[tr],lam);diagnostics.append(dict(outer_fold=fold,inner_fold=inner,scope='inner',**fitted[2]))
                    pred=predict_count(train.iloc[tr],train.iloc[va],'nb2','full',fitted);losses.extend(pred.nll.tolist())
                inner_scores[lam]=float(np.mean(losses))
            # Predetermined deterministic tie preference: existing lambda=1.
            chosen=min(LAMBDAS,key=lambda x:(inner_scores[x],abs(x-1)))
            choices.append(dict(outer_fold=fold,chosen_lambda=chosen,inner_pooled_nll={str(k):v for k,v in inner_scores.items()}))
            for lam in LAMBDAS:
                fitted=fit(train,lam);diagnostics.append(dict(outer_fold=fold,inner_fold=None,scope='outer',**fitted[2]))
                pred=predict_count(train,test,'nb2','full',fitted);pred['route']='expID';pred['fold']=fold;pred['model']=f'NB2_lambda_{lam:g}';records.append(pred)
                if lam==chosen:
                    p=pred.copy();p['model']='nested_penalty';records.append(p)
            print('LIMITED OUTER FOLD',fold,'chosen',chosen,flush=True)
    z=pd.concat(records,ignore_index=True);z.to_csv(OUT/'limited_oof.csv',index=False)
    score=count_scores(z);score.to_csv(OUT/'limited_validation.csv',index=False)
    count_scores(z.assign(route=z.fold.astype(str))).to_csv(OUT/'limited_fold_validation.csv',index=False)
    (OUT/'selection.json').write_text(json.dumps(choices,indent=2),encoding='utf-8')
    (OUT/'fit_stability.json').write_text(json.dumps(diagnostics,indent=2),encoding='utf-8')
    old=pd.read_csv(ROOT/'results/q3/q3_stage3_20261127T125020Z/count_oof.csv').query("route=='expID' and model=='hurdle_nb2_full'").sort_values('source_row_id')
    base=z[z.model=='NB2_lambda_1'].sort_values('source_row_id');assert np.allclose(base.nll,old.nll,atol=1e-7)
    assert z.groupby('model').source_row_id.nunique().eq(278).all()
    meta=dict(stage='R2-5',input_sha256=hashlib.sha256(INPUT.read_bytes()).hexdigest(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        lambdas=LAMBDAS,outer='original_expID_fivefold',inner='training_only_expID_threefold',inherited_environment='R2_2/metadata.json',
        penalty='total positive likelihood; all slopes; unpenalized intercept and logalpha',seed=20261127,
        acceptance=dict(original_lambda1_reproduced=True,OOF_each_row_once_per_model=True),
        uncertainty='No selection-aware bootstrap generated; prior fixed-lambda1 intervals cannot describe nested flow')
    (OUT/'metadata.json').write_text(json.dumps(meta,indent=2),encoding='utf-8');(OUT/'implementation_snapshot.py').write_bytes(Path(__file__).read_bytes())
    pd.DataFrame([dict(branch='NB2_penalty',candidate=lam,outer='expID5',inner='expID3',gate='C1_fixed',family='zero_truncated_NB2') for lam in LAMBDAS]).to_csv(OUT/'limited_experiment_matrix.csv',index=False)
    print(score.to_string(index=False),flush=True)


if __name__=='__main__':run()
