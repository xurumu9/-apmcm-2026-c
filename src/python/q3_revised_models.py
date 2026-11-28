"""Independent Q3 stages 1/2; preserves the first-run implementation and results."""
import argparse
import hashlib
import json
import warnings
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.spatial import ConvexHull,QhullError
from sklearn.metrics import log_loss
from sklearn.model_selection import GroupKFold,LeaveOneGroupOut
import statsmodels.api as sm
from q3_playback_analysis import ROOT,INPUT,TYPES,CONTEXTS,FLAGS,COMBOS,COLS,combo,design,fit_combo,predict_combo


def support(a,point):
    if len(a)<2:return 'support_unverified'
    center=a.mean(0);scale=a.std(0);scale[scale<1e-10]=1
    z=(a-center)/scale;p=(point-center)/scale
    _,s,v=np.linalg.svd(z,full_matrices=False);rank=int(np.sum(s>1e-8))
    if rank==0:return 'boundary' if np.linalg.norm(p)<1e-7 else 'extrapolation'
    basis=v[:rank].T
    if np.linalg.norm(p-p@basis@basis.T)>1e-7:return 'extrapolation'
    zz=z@basis;pp=p@basis
    if rank==1:
        distances=np.array([pp[0]-zz[:,0].max(),zz[:,0].min()-pp[0]])
    else:
        try:
            hull=ConvexHull(zz);distances=hull.equations[:,:-1]@pp+hull.equations[:,-1]
        except QhullError:return 'support_unverified'
    if distances.max()>1e-7:return 'extrapolation'
    return 'boundary' if np.any(np.abs(distances)<1e-7) else 'interpolation'


def stage1():
    d=pd.read_csv(INPUT);run=datetime.now(timezone.utc).strftime('q3_stage1_%Y%m%dT%H%M%SZ')
    out=ROOT/'results/q3'/run;out.mkdir(parents=True,exist_ok=False)
    assert d.shape==(278,40) and (d.groupby('expID').size()==2).all()
    tracks=d[d.Type=='call'].set_index('expID').PlaybackTrack.to_dict()
    assert len(tracks)==139
    conflict={b:((d[b+'YesNo']==0)&d[b+'Latency'].notna()) for b in ['HeadsUp','Vocal','Approach']}
    masks={'combo_all_v1':np.ones(len(d),bool),'count_actual_v1':np.ones(len(d),bool)}
    for b in conflict:masks['latency_'+b+'_v1']=(~conflict[b]).to_numpy()
    rows=[];populations=[]
    for name,mask in masks.items():
        sub=d[mask]
        populations.append(dict(analysis_population_id=name,n=len(sub),event_definition_id='actual_count_positive' if name.startswith('count') else 'original_HVA_flags',
            share_full_combo_probability=name in ['combo_all_v1','latency_HeadsUp_v1'],
            event_n=int((sub.VocalNcalls>0).sum()) if name.startswith('count') else int(sub[name.split('_')[1]+'YesNo'].sum()) if name.startswith('latency') else int(sub.ResponseYesNo.sum())))
        for i in np.flatnonzero(mask):rows.append(dict(analysis_population_id=name,source_row_id=i+1,exp_id=d.expID.iloc[i],natural_track=tracks[d.expID.iloc[i]]))
    pd.DataFrame(rows).to_csv(out/'analysis_membership.csv',index=False)
    pd.DataFrame(populations).to_csv(out/'population_definitions.csv',index=False)
    clean=d.copy();clean.insert(0,'source_row_id',np.arange(1,len(d)+1));clean['analysis_rule']='original_flags_v1';clean['natural_track_group']=clean.expID.map(tracks)
    for b in conflict:clean[b+'_latency_conflict']=conflict[b]
    clean.to_csv(out/'analysis_snapshot.csv',index=False)
    support_rows=[]
    for name,mask in masks.items():
        for t in TYPES:
            for c in CONTEXTS:
                sub=d[mask&(d.CallType==t)&(d.Context==c)]
                event_n=int((sub.VocalNcalls>0).sum()) if name.startswith('count') else int(sub[name.split('_')[1]+'YesNo'].sum()) if name.startswith('latency') else int(sub.ResponseYesNo.sum())
                for distance in [50,100,150]:
                    distance_support='support_unverified' if not len(sub) else 'extrapolation' if distance<sub.Distance.min() or distance>sub.Distance.max() else 'boundary' if distance in [sub.Distance.min(),sub.Distance.max()] else 'interpolation'
                    point=np.array([distance,8,0]);a=sub[COLS[2:]].to_numpy(float)
                    joint=support(a,point)
                    row=dict(analysis_population_id=name,call_type=t,context=c,distance_m=distance,n_penguins=8,vocal_ncalls_before=0,
                        distance_support=distance_support,joint_support=joint,effective_n=len(sub),event_n=event_n,
                        observation_window_s=60,extrapolation_reason='outside_observed_joint_covariate_support' if joint=='extrapolation' else '')
                    for col in COLS[2:]:row[col+'_min']=sub[col].min();row[col+'_max']=sub[col].max()
                    support_rows.append(row)
    pd.DataFrame(support_rows).to_csv(out/'representative_support.csv',index=False)
    baseline=json.loads((ROOT/'results/q3/q3_20261127T110928Z/metadata.json').read_text())
    meta=dict(run_id=run,input_sha256=hashlib.sha256(INPUT.read_bytes()).hexdigest(),
              script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              reused_outer_folds=baseline['folds'],numeric_support_tolerance=1e-7,
              support_definition='Convex hull in affine subspace, scaling only for geometry; not reused in models.',
              pending_manual_checks=['duration60 coding and per-record upper bound','zero-time resolution','latency/flag conflicts','track identity vs underlying recording'],
              note='Only analysis population definitions frozen; disputed biological meanings not resolved.')
    (out/'metadata.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    print('STAGE1',out);print(pd.DataFrame(populations).to_string(index=False))
    print('SUPPORT',pd.DataFrame(support_rows).query("analysis_population_id=='combo_all_v1'").joint_support.value_counts().to_dict())


def scores(y,p):
    one=np.array([[float(c==v) for c in COMBOS] for v in y]);event=(np.array(y)!='000').astype(int)
    return dict(multiclass_logloss=log_loss(y,p,labels=COMBOS),multiclass_brier=float(np.mean(np.sum((one-p)**2,axis=1))),
                any_response_brier=float(np.mean((event-(1-p[:,0]))**2)))


def gee_fit(train,test,structure):
    trans=design();x=sm.add_constant(trans.fit_transform(train[COLS]),has_constant='add');xt=sm.add_constant(trans.transform(test[COLS]),has_constant='add')
    cov=sm.cov_struct.Exchangeable() if structure=='exchangeable' else sm.cov_struct.Independence()
    model=sm.GEE(train.ResponseYesNo.to_numpy(),x,groups=train.expID.to_numpy(),family=sm.families.Binomial(),cov_struct=cov)
    fitted=model.fit(maxiter=200,cov_type='robust')
    assert fitted.converged and np.isfinite(fitted.params).all()
    return fitted.predict(xt),fitted,['Intercept']+trans.get_feature_names_out().tolist()


def stage2(stage1_path):
    folder=Path(stage1_path);meta=json.loads((folder/'metadata.json').read_text());d=pd.read_csv(INPUT)
    assert meta['input_sha256']==hashlib.sha256(INPUT.read_bytes()).hexdigest()
    folds=[(np.array(f['train_rows'])-1,np.array(f['test_rows'])-1) for f in meta['reused_outer_folds']]
    out=ROOT/'results/q3'/datetime.now(timezone.utc).strftime('q3_stage2_%Y%m%dT%H%M%SZ');out.mkdir(parents=True,exist_ok=False)
    records=[];predictions=[];selection=[];warning_log=[];y=combo(d)
    routes={'expID':folds,'natural_track':list(GroupKFold(5).split(d,groups=d.natural_track_group if 'natural_track_group' in d else d.expID.map(d[d.Type=='call'].set_index('expID').PlaybackTrack))),
            'date':list(LeaveOneGroupOut().split(d,groups=d.Date))}
    for route,split in routes.items():
        probs={label:np.zeros((len(d),8)) for label in ['fixed_C1','nested_C']}
        covered=np.zeros(len(d),int)
        for fold,(tr,te) in enumerate(split):
            train=d.iloc[tr];test=d.iloc[te];assert not set(train.expID)&set(test.expID);covered[te]+=1
            if route=='date':assert not set(train.Date)&set(test.Date)
            trackmap=d[d.Type=='call'].set_index('expID').PlaybackTrack
            if route=='natural_track':assert not set(train.expID.map(trackmap))&set(test.expID.map(trackmap))
            inner_scores=[]
            for C in [.25,1,4]:
                ip=np.zeros((len(train),8))
                for it,iv in GroupKFold(3).split(train,groups=train.expID):
                    with warnings.catch_warnings(record=True) as caught:
                        warnings.simplefilter('always');m=fit_combo(train.iloc[it],C)
                    warning_log.extend(str(w.message) for w in caught)
                    ip[iv]=predict_combo(m,train.iloc[iv])
                inner_scores.append(log_loss(combo(train),ip,labels=COMBOS))
            C=[.25,1,4][int(np.argmin(inner_scores))]
            selection.append(dict(route=route,fold=fold,C=C,inner_scores=inner_scores,train_rows=(tr+1).tolist(),test_rows=(te+1).tolist()))
            for label,value in [('fixed_C1',1),('nested_C',C)]:probs[label][te]=predict_combo(fit_combo(train,value),test)
        assert np.all(covered==1)
        for label,p in probs.items():
            records.append(dict(task='multiclass',route=route,model=label,**scores(y,p)))
            for i in range(len(d)):
                predictions.append(dict(route=route,model=label,source_row_id=i+1,exp_id=int(d.expID.iloc[i]),actual_combo=y.iloc[i],**{'p_'+c:p[i,j] for j,c in enumerate(COMBOS)}))
        print('COMBO',route,records[-2:],flush=True)
    coefficients=[];binary_oof=[]
    for structure in ['exchangeable','independence']:
        p=np.zeros(len(d))
        for tr,te in folds:p[te],_,_=gee_fit(d.iloc[tr],d.iloc[te],structure)
        event=d.ResponseYesNo.to_numpy()
        for i in range(len(d)):binary_oof.append(dict(model='GEE_'+structure,source_row_id=i+1,exp_id=int(d.expID.iloc[i]),actual=int(event[i]),probability=float(p[i])))
        records.append(dict(task='binary',route='expID',model='GEE_'+structure,binary_logloss=log_loss(event,p),binary_brier=float(np.mean((event-p)**2))))
        _,fitted,names=gee_fit(d,d,structure);ci=fitted.conf_int()
        for i,name in enumerate(names):coefficients.append(dict(structure=structure,term=name,log_odds=fitted.params[i],robust_se=fitted.bse[i],lower=ci[i,0],upper=ci[i,1],
            correlation=float(fitted.cov_struct.dep_params) if structure=='exchangeable' else 0))
    pd.DataFrame(records).to_csv(out/'validation.csv',index=False);pd.DataFrame(predictions).to_csv(out/'oof_combinations.csv',index=False)
    pd.DataFrame(coefficients).to_csv(out/'gee_associations.csv',index=False)
    pd.DataFrame(binary_oof).to_csv(out/'gee_oof_predictions.csv',index=False)
    oof=pd.DataFrame(predictions);calibration=[]
    for (route,model),sub in oof.groupby(['route','model']):
        prob=1-sub.p_000;actual=(sub.actual_combo!='000').astype(int)
        for left in np.arange(0,1,.2):
            mask=(prob>=left)&(prob<left+.2+1e-12)
            calibration.append(dict(route=route,model=model,bin_left=left,n=int(mask.sum()),predicted=prob[mask].mean(),observed=actual[mask].mean()))
    pd.DataFrame(calibration).to_csv(out/'calibration.csv',index=False)
    detailed_calibration=[]
    for (route,model),sub in oof.groupby(['route','model']):
        for c in COMBOS:
            prob=sub['p_'+c];actual=(sub.actual_combo==c).astype(int)
            for left in np.arange(0,1,.2):
                mask=(prob>=left)&(prob<left+.2)
                detailed_calibration.append(dict(task='multiclass',route=route,model=model,category=c,bin_left=left,
                    n=int(mask.sum()),predicted=prob[mask].mean(),observed=actual[mask].mean()))
    for model,sub in pd.DataFrame(binary_oof).groupby('model'):
        for left in np.arange(0,1,.2):
            mask=(sub.probability>=left)&(sub.probability<left+.2)
            detailed_calibration.append(dict(task='binary',route='expID',model=model,category='any_response',bin_left=left,
                n=int(mask.sum()),predicted=sub.probability[mask].mean(),observed=sub.actual[mask].mean()))
    pd.DataFrame(detailed_calibration).to_csv(out/'outcome_calibration.csv',index=False)
    grid=pd.read_csv(folder/'representative_support.csv').query("analysis_population_id=='combo_all_v1'").reset_index(drop=True)
    covariates=pd.DataFrame(dict(CallType=grid.call_type,Context=grid.context,Distance=grid.distance_m,Npenguins=grid.n_penguins,VocalNcallsBefore=grid.vocal_ncalls_before))
    gp=predict_combo(fit_combo(d,1),covariates);grid_predictions=[]
    for k,row in grid.iterrows():
        for j,c in enumerate(COMBOS):grid_predictions.append(dict(**row.to_dict(),combo=c,probability=gp[k,j],model_version='stage2_fixed_C1',interval_method='deferred_to_stage6'))
    pd.DataFrame(grid_predictions).to_csv(out/'combination_predictions.csv',index=False)
    result=dict(stage1_run=str(folder),input_sha256=meta['input_sha256'],script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                selections=selection,warnings=warning_log,models='C1 and inner-expID-3fold C [.25,1,4]; GEE robust Binomial logit',
                note='Stage 2 only. No bootstrap confidence/prediction intervals generated; reserved for frozen stage 6. No random effects fitted. Unseen training classes assigned zero then logloss numerically clipped by sklearn; rare-class limitation retained from baseline.')
    (out/'metadata.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('STAGE2',out);print(pd.DataFrame(records).to_string(index=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['1','2']);parser.add_argument('--stage1');args=parser.parse_args()
    if args.stage=='1':stage1()
    else:
        if not args.stage1:parser.error('--stage1 required')
        stage2(args.stage1)
