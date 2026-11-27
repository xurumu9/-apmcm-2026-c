"""Stage 2: fixed Logistic fallback with two training scopes; no tuning."""
import csv
import hashlib
import importlib.util
import json
import platform
import subprocess
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import sklearn
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT=Path(__file__).resolve().parents[2]
INPUT=ROOT/'data/raw/acoustics/Data01_AfricanPenguins_seasurface_calls_acoustics.csv'
FEATURES=('Duration','F01','Fpeak','Q25','Q50','Q75')
LABELS=('flat','mod','tv')


def write_csv(path,rows):
    with path.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def main():
    raw=list(csv.DictReader(INPUT.open(encoding='utf-8-sig',newline='')))
    x=np.array([[float(r[k]) for k in FEATURES] for r in raw]);y=np.array([r['CallType'] for r in raw])
    dates=np.array([r['Date'] for r in raw])
    missing=lambda v:v.strip().lower() in {'','na','nan','null'}
    f02=np.array([not missing(r['F02']) for r in raw]);pulse=np.array([not missing(r['PulseRate']) for r in raw])
    fallback=~f02&~pulse
    assert x.shape==(108,6) and np.isfinite(x).all() and fallback.sum()==50
    # Reuse Stage 1's actual split indices; no same-date record can enter training.
    stage1_path=ROOT/'results/q1/common_feature_run_metadata.json'
    stage1=json.loads(stage1_path.read_text(encoding='utf-8'))
    assert stage1['input_sha256']==hashlib.sha256(INPUT.read_bytes()).hexdigest()
    splits=[(np.array(s['train_source_rows'])-1,np.array(s['test_source_rows'])-1)
            for s in stage1['splits'] if s['validation']=='leave_one_date_out']
    coverage=np.zeros(len(y),int)
    for train,test in splits:
        assert not set(train)&set(test) and not set(dates[train])&set(dates[test])
        coverage[test]+=1
    assert len(splits)==16 and np.all(coverage==1)
    baseline=np.where(f02,'tv',np.where(pulse,'mod','flat'))
    predictions={'structure_rule':baseline};probabilities={};fold_rows=[];warn=[]
    for scope in ['all_flat_mod','double_missing_only']:
        pred=baseline.copy();prob=np.full(len(y),np.nan)
        for fold,(outer_train,test) in enumerate(splits):
            train=outer_train[np.isin(y[outer_train],['flat','mod'])]
            if scope=='double_missing_only':train=train[fallback[train]]
            target=test[fallback[test]]
            assert set(y[train])=={'flat','mod'}
            estimator=make_pipeline(StandardScaler(),LogisticRegression(C=1,penalty='l2',solver='lbfgs',
                                    max_iter=3000,class_weight=None,random_state=42))
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always');estimator.fit(x[train],y[train])
            for w in caught:warn.append(dict(scope=scope,fold=fold,category=w.category.__name__,message=str(w.message)))
            if any(issubclass(w.category,ConvergenceWarning) for w in caught):raise RuntimeError('Convergence failure')
            assert np.allclose(estimator[0].mean_,x[train].mean(0))
            assert estimator[-1].classes_.tolist()==['flat','mod']
            if len(target):
                prob[target]=estimator.predict_proba(x[target])[:,1]
                pred[target]=np.where(prob[target]>=.5,'mod','flat')
            fold_rows.append(dict(scope=scope,fold=fold,test_date=dates[test[0]],train_n=len(train),
                                  train_flat=int(np.sum(y[train]=='flat')),train_mod=int(np.sum(y[train]=='mod')),
                                  fallback_test_n=len(target),train_source_rows=(train+1).tolist(),
                                  test_source_rows=(test+1).tolist(),scaler_mean=estimator[0].mean_.tolist()))
        assert np.all(np.isfinite(prob[fallback])) and np.array_equal(pred[~fallback],baseline[~fallback])
        predictions[scope]=pred;probabilities[scope]=prob
    # Reproduce the unmodified prior two-stage model as a distinct comparator.
    path=ROOT/'src/python/q1_weighted_classifier.py'
    spec=importlib.util.spec_from_file_location('existing_q1_weighted',path)
    old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    old_x,old_y,old_dates,old_f02,_=old.load_data()
    assert np.array_equal(y,old_y) and np.array_equal(dates,old_dates)
    predictions['existing_two_stage']=old.cross_validate(old_x,old_y,old_f02,splits)
    run_id=datetime.now(timezone.utc).strftime('q1_hybrid_stage2_%Y%m%dT%H%M%SZ')
    out=ROOT/'results/q1'/run_id;out.mkdir(parents=True,exist_ok=False)
    metrics=[];oof=[];date_rows=[]
    for name,pred in predictions.items():
        fixes=(pred==y)&(baseline!=y);introduced=(pred!=y)&(baseline==y)
        record=dict(model=name,n=108,accuracy=accuracy_score(y,pred),macro_f1=f1_score(y,pred,labels=LABELS,average='macro',zero_division=0),
                    balanced_accuracy=balanced_accuracy_score(y,pred),
                    flat_recall=float(np.mean(pred[y=='flat']=='flat')),mod_recall=float(np.mean(pred[y=='mod']=='mod')),
                    tv_recall=float(np.mean(pred[y=='tv']=='tv')),missing_mod_correct=int(np.sum((pred=='mod')&(y=='mod')&fallback)),
                    flat_errors=int(np.sum((pred!='flat')&(y=='flat'))),fixed_original_errors=int(fixes.sum()),
                    introduced_errors=int(introduced.sum()),net_correct_change=int(fixes.sum()-introduced.sum()),
                    fallback_accuracy=accuracy_score(y[fallback],pred[fallback]),
                    fallback_macro_f1=f1_score(y[fallback],pred[fallback],labels=['flat','mod'],average='macro',zero_division=0),
                    confusion_matrix=confusion_matrix(y,pred,labels=LABELS).tolist())
        metrics.append(record)
        for i,r in enumerate(raw):
            probability=probabilities[name][i] if name in probabilities else np.nan
            oof.append(dict(run_id=run_id,model=name,source_row_id=i+1,date=dates[i],true_label=y[i],predicted_label=pred[i],
                            route='f02_tv' if f02[i] else 'pulse_mod' if pulse[i] else 'double_missing',
                            fallback_probability_mod=float(probability) if np.isfinite(probability) else '',
                            corrected_original_error=bool(fixes[i]),introduced_error=bool(introduced[i])))
        for d in sorted(set(dates),key=lambda s:datetime.strptime(s,'%d/%m/%Y')):
            mask=dates==d
            date_rows.append(dict(model=name,date=d,n=int(mask.sum()),correct=int(np.sum(pred[mask]==y[mask])),
                                  corrected_original_errors=int(fixes[mask].sum()),introduced_errors=int(introduced[mask].sum())))
    write_csv(out/'metrics.csv',metrics);write_csv(out/'oof_predictions.csv',oof);write_csv(out/'date_diagnostics.csv',date_rows)
    head=subprocess.check_output(['git','-c','safe.directory='+str(ROOT),'rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    meta=dict(run_id=run_id,git_head=head,input_sha256=hashlib.sha256(INPUT.read_bytes()).hexdigest(),
              script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              comparator_script_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
              stage1_metadata_sha256=hashlib.sha256(stage1_path.read_bytes()).hexdigest(),
              versions=dict(python=platform.python_version(),numpy=np.__version__,sklearn=sklearn.__version__),
              parameters=dict(C=1,penalty='l2',solver='lbfgs',max_iter=3000,class_weight=None,random_state=42,threshold=.5),
              features=FEATURES,folds=fold_rows,warnings=warn,
              note='New code uncommitted; identify script by hash. 32 new binary fits and existing comparator reproduced on identical 16 outer dates. No search or PCA.',
              limitation='Exploratory conditional classification dependent on structural recording status. Different training scopes imply different distributions. Not independent unknown-audio recognition performance.')
    (out/'metadata.json').write_text(json.dumps(meta,indent=2,ensure_ascii=False),encoding='utf-8')
    print('OUTPUT',out)
    print(json.dumps(metrics,indent=2))
    print('SIX',[(r['model'],r['source_row_id'],r['predicted_label'],r['fallback_probability_mod']) for r in oof
                 if r['source_row_id'] in [10,49,79,105,107,108]])
    print('WARNINGS',warn)


if __name__=='__main__':main()
