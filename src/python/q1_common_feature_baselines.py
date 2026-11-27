"""Stage 1: fixed six-feature baselines, shared splits, exploratory OOF evaluation."""
import csv
import hashlib
import inspect
import json
import os
import platform
import subprocess
import tempfile
import warnings
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "apmcm_q1_baselines"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import sklearn
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score, precision_recall_fscore_support
from sklearn.model_selection import LeaveOneGroupOut, StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "data/raw/acoustics/Data01_AfricanPenguins_seasurface_calls_acoustics.csv"
FEATURES = ("Duration", "F01", "Fpeak", "Q25", "Q50", "Q75")
LABELS = ("flat", "mod", "tv")
SEEDS = (1, 2, 3, 4, 42)


def models():
    options = dict(C=1, penalty="l2", solver="lbfgs", max_iter=3000, class_weight=None)
    if "multi_class" in inspect.signature(LogisticRegression).parameters:
        options["multi_class"] = "multinomial"
    return dict(B0=DummyClassifier(strategy="most_frequent"),
                B1=make_pipeline(StandardScaler(), LogisticRegression(**options)),
                B2=make_pipeline(StandardScaler(), SVC(C=1, kernel="rbf", gamma=1/6,
                                  tol=.001, probability=False, class_weight=None)),
                B3=RandomForestClassifier(n_estimators=200,max_depth=3,min_samples_leaf=5,
                    min_samples_split=2,max_features="sqrt",bootstrap=True,random_state=42,
                    class_weight=None,n_jobs=1))


def csv_write(path, rows):
    with path.open("w",encoding="utf-8",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def metrics(y, pred):
    result=dict(accuracy=accuracy_score(y,pred),macro_f1=f1_score(y,pred,labels=LABELS,average="macro",zero_division=0),
                balanced_accuracy=balanced_accuracy_score(y,pred))
    precision,recall,_,support=precision_recall_fscore_support(y,pred,labels=LABELS,zero_division=0)
    for i,label in enumerate(LABELS):
        result.update({label+"_precision":precision[i],label+"_recall":recall[i],label+"_n":int(support[i])})
    result['flat_errors']=int(np.sum((y=='flat')&(pred!='flat')))
    return result


def main():
    out=ROOT/'results/q1';figures=ROOT/'figures';report=ROOT/'experiments/reports/q1_common_feature_baselines.md'
    paths=[out/n for n in ['classification_metrics.csv','common_feature_oof_predictions.csv',
           'common_feature_run_metadata.json','common_feature_date_errors.csv','common_feature_mod_diagnostics.csv']]
    paths += [figures/'q1_common_feature_confusions.png',figures/'q1_common_feature_date_errors.png',report]
    if any(p.exists() for p in paths):raise FileExistsError('Refusing to overwrite existing baseline artifacts')
    with INPUT.open(encoding='utf-8-sig',newline='') as f:raw=list(csv.DictReader(f))
    # No structural measurements, missing indicators, IDs or dates enter X.
    x=np.array([[float(r[k]) for k in FEATURES] for r in raw])
    y=np.array([r['CallType'].strip().lower() for r in raw]);dates=np.array([r['Date'].strip() for r in raw])
    assert x.shape==(108,6) and np.isfinite(x).all() and set(y)==set(LABELS)
    run_id=datetime.now(timezone.utc).strftime('q1_common_%Y%m%dT%H%M%SZ')
    specifications=[('leave_one_date_out',None,list(LeaveOneGroupOut().split(x,y,dates)))]
    specifications += [('stratified_5fold',seed,list(StratifiedKFold(5,shuffle=True,random_state=seed).split(x,y))) for seed in SEEDS]
    results=[];oof=[];date_rows=[];predictions={};warning_rows=[];splits=[];params={}
    for validation,seed,folds in specifications:
        coverage=np.zeros(len(y),int)
        for fold,(train,test) in enumerate(folds):
            assert not set(train)&set(test) and set(y[train])==set(LABELS)
            if validation=='leave_one_date_out':assert not set(dates[train])&set(dates[test])
            coverage[test]+=1
            splits.append(dict(validation=validation,seed=seed,fold=fold,
                               train_source_rows=(train+1).tolist(),test_source_rows=(test+1).tolist()))
        assert np.all(coverage==1)
        for name in models():
            pred=np.full(len(y),'',dtype='<U4')
            for fold,(train,test) in enumerate(folds):
                estimator=models()[name]
                params[name]=estimator.get_params(deep=True)
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter('always');estimator.fit(x[train],y[train])
                for w in caught:
                    warning_rows.append(dict(model=name,validation=validation,seed=seed,fold=fold,
                                             category=w.category.__name__,message=str(w.message)))
                if any(issubclass(w.category,ConvergenceWarning) for w in caught):
                    raise RuntimeError(f'Convergence failure: {name}/{validation}/{seed}/{fold}')
                if name in ('B1','B2'):
                    assert np.allclose(estimator[0].mean_,x[train].mean(0))
                pred[test]=estimator.predict(x[test])
                for i in test:
                    oof.append(dict(run_id=run_id,model=name,validation=validation,seed=seed,fold=fold,
                                    source_row_id=int(i+1),date=dates[i],true_label=y[i],predicted_label=pred[i]))
            assert set(pred).issubset(LABELS)
            results.append(dict(run_id=run_id,model=name,validation=validation,seed=seed,**metrics(y,pred)))
            predictions[name,validation,seed]=pred
            if validation=='leave_one_date_out':
                for d in sorted(set(dates),key=lambda s:datetime.strptime(s,'%d/%m/%Y')):
                    mask=dates==d;n=int(mask.sum());errors=int(np.sum(pred[mask]!=y[mask]))
                    date_rows.append(dict(model=name,date=d,n=n,correct=n-errors,errors=errors,error_rate=errors/n))
            print(name,validation,seed,results[-1]['macro_f1'],flush=True)
    # Structural status is accessed only after all classification fits, for diagnosis.
    missing=np.array([r['PulseRate'].strip().lower() in {'','na','nan','null'} for r in raw])
    diagnostics=[]
    for (name,validation,seed),pred in predictions.items():
        for group,mask in [('mod_recorded',(y=='mod')&~missing),('mod_missing',(y=='mod')&missing)]:
            diagnostics.append(dict(model=name,validation=validation,seed=seed,group=group,n=int(mask.sum()),
                                    mod_correct=int(np.sum(pred[mask]=='mod')),mod_recall=float(np.mean(pred[mask]=='mod'))))
    out.mkdir(parents=True,exist_ok=True);figures.mkdir(parents=True,exist_ok=True)
    csv_write(paths[0],results);csv_write(paths[1],oof);csv_write(paths[3],date_rows);csv_write(paths[4],diagnostics)
    head=subprocess.check_output(['git','-c','safe.directory='+str(ROOT),'rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    metadata=dict(run_id=run_id,input_sha256=hashlib.sha256(INPUT.read_bytes()).hexdigest(),
                  script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),git_head=head,
                  code_state='Script uncommitted at initial run; identify with script SHA256.',
                  features=FEATURES,labels=LABELS,seeds=SEEDS,parameters=params,splits=splits,warnings=warning_rows,
                  fits=sum(len(f) for _,_,f in specifications)*4,
                  versions=dict(python=platform.python_version(),numpy=np.__version__,sklearn=sklearn.__version__,matplotlib=matplotlib.__version__),
                  validation='Pooled 108 OOF predictions per model and validation seed; no foldwise macro averaging.',
                  preprocessing='Fresh training-fold scaler for B1/B2; no reuse of diagnostic PCA/scalers. No feature selection, search, resampling, weights or tuning.',
                  limitation='Exploratory internal validation after prior data inspection. No external test. Date not individual identity. Highest outer score not unbiased selected-model performance.')
    paths[2].write_text(json.dumps(metadata,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    fig,axes=plt.subplots(2,2,figsize=(9,8),layout='constrained')
    for ax,name in zip(axes.flat,models()):
        cm=confusion_matrix(y,predictions[name,'leave_one_date_out',None],labels=LABELS)
        ax.imshow(cm,cmap='Blues',vmin=0,vmax=44)
        for (i,j),v in np.ndenumerate(cm):ax.text(j,i,str(v),ha='center',va='center',color='white' if v>22 else 'black')
        ax.set_xticks(range(3),LABELS);ax.set_yticks(range(3),LABELS)
        ax.set_xlabel('Predicted');ax.set_ylabel('Actual');ax.set_title(name+' | leave-one-date-out')
    fig.savefig(paths[5],dpi=180);plt.close(fig)
    ds=sorted(set(dates),key=lambda s:datetime.strptime(s,'%d/%m/%Y'))
    fig,(a,b)=plt.subplots(2,1,figsize=(11,7),sharex=True,layout='constrained')
    a.bar(range(len(ds)),[int(np.sum(dates==d)) for d in ds]);a.set_ylabel('Recordings')
    for name in models():b.plot(range(len(ds)),[next(r['error_rate'] for r in date_rows if r['model']==name and r['date']==d) for d in ds],marker='o',label=name)
    b.set_xticks(range(len(ds)),ds,rotation=55,ha='right');b.set_ylabel('Error rate');b.legend(ncol=4)
    fig.savefig(paths[6],dpi=180);plt.close(fig)
    lines=['# 六共同声学特征三分类基线：阶段 1','',f'运行日期：2026-11-27；run_id `{run_id}`。未调参，未执行阶段 2/3。',
           '', 'B0 多数类，B1 多项 Logistic，B2 RBF-SVM，B3 浅层随机森林。参数与划分沿用 [实验设计](q1_classification_design.md)。',
           '', '## 日期留组结果（汇总 108 条折外预测）','', '| 模型 | Accuracy | Macro-F1 | Balanced Accuracy | flat Recall | mod Recall | tv Recall | flat 错误数 |','|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in results:
        if r['validation']=='leave_one_date_out':
            lines.append('| '+r['model']+' | '+' | '.join(f'{r[k]:.4f}' for k in ['accuracy','macro_f1','balanced_accuracy','flat_recall','mod_recall','tv_recall'])+f" | {r['flat_errors']} |")
    lines+=['','## 重复分层五折（每种子先汇总，再求均值和范围）','','| 模型 | Accuracy 均值 [最小, 最大] | Macro-F1 均值 [最小, 最大] |','|---|---|---|']
    for name in models():
        rr=[r for r in results if r['model']==name and r['validation']=='stratified_5fold']
        cells=[]
        for k in ['accuracy','macro_f1']:
            v=[r[k] for r in rr];cells.append(f'{np.mean(v):.4f} [{min(v):.4f}, {max(v):.4f}]')
        lines.append('| '+name+' | '+' | '.join(cells)+' |')
    lines+=['','## Mod 子集诊断（日期留组，仅诊断不选模）','','| 模型 | 有记录 Mod 正确数/34 | 缺失 Mod 正确数/6 |','|---|---:|---:|']
    for name in models():
        dd=[r for r in diagnostics if r['model']==name and r['validation']=='leave_one_date_out']
        lines.append(f"| {name} | {dd[0]['mod_correct']} | {dd[1]['mod_correct']} |")
    lines+=['','全部逐条预测及日期错误表位于本地 results/q1/common_feature_*.csv，指标为 classification_metrics.csv；输入/代码哈希、软件版本、41 个统一划分及警告记录见 common_feature_run_metadata.json。',
            '', '结论只能反映固定候选在本数据上的探索性内部验证。没有外部测试；日期不是个体，反复观察数据的影响仍存在。最高外层分数不等于无偏最优模型性能；未对六条困难记录调参、加权或删除。']
    report.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('RUN',run_id,'FITS',metadata['fits'],'WARNINGS',len(warning_rows))


if __name__=='__main__':
    main()
