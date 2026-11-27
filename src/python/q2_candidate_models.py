"""Exploratory Q2 candidates for team review, NOT a finalized competition model.

The input is an aggregate summary; rows are NOT treated as independent samples.
Outputs under results/q2 are ignored by Git and are generated locally.
"""
from pathlib import Path
import csv, hashlib, json, platform
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
INPUT=ROOT/'experiments/reports/q2_2_descriptive_summary.csv'
OUT=ROOT/'results/q2'
DIST=np.array([4.,8.,16.,32.,64.,128.,256.])
CALLS=('flat','mod','tv'); METRICS=('spectrogram','amplitude_spectrum','envelope')
WEIGHTS={'equal':(.3333333333333333,)*3,'spectrogram_priority':(.6,.2,.2),
         'spectrum_priority':(.2,.6,.2),'envelope_priority':(.2,.2,.6)}
LEVELS=((.3,'potential'),(.5,'recognition'),(.7,'reliable'))
TAUS=np.geomspace(4,2048,400)

def read_data():
    values={}
    with INPUT.open(encoding='utf-8',newline='') as f:
        for r in csv.DictReader(f):
            key=(r['call_type'],r['metric'],int(r['distance_m']))
            if key in values: raise ValueError('duplicate summary group')
            y=float(r['mean'])
            if not 0<=y<=1: raise ValueError('mean outside [0,1]')
            values[key]=y
    return {c:np.array([[values[(c,m,int(d))] for d in DIST] for m in METRICS]) for c in CALLS}

def isotonic(y):
    # Equal weight per observed distance; PAVA constrained to non-increasing.
    blocks=[]
    for value in y:
        blocks.append([float(value),1])
        while len(blocks)>1 and blocks[-2][0] < blocks[-1][0]:
            b=blocks.pop();a=blocks.pop();n=a[1]+b[1]
            blocks.append([(a[0]*a[1]+b[0]*b[1])/n,n])
    return np.array([x for value,n in blocks for x in [value]*n])

def exponential(x,y):
    # y=a+b*exp(-d/tau); minimize SSE over 0<=a, 0<=b, a+b<=1.
    best=None
    for tau in TAUS:
        z=np.exp(-x/tau); mat=np.column_stack([np.ones(len(x)),z])
        a,b=np.linalg.lstsq(mat,y,rcond=None)[0]; candidates=[]
        if a>=0 and b>=0 and a+b<=1: candidates.append((a,b))
        candidates.append((0.,float(np.clip(z@y/(z@z),0,1))))
        candidates.append((float(np.clip(np.mean(y),0,1)),0.))
        b1=float(np.clip((z-1)@(y-1)/((z-1)@(z-1)),0,1)); candidates.append((1-b1,b1))
        for a,b in candidates:
            sse=float(np.sum((y-a-b*z)**2))
            if best is None or sse<best[0]:best=(sse,float(a),float(b),float(tau))
    return best[1:]

def predict(method,x,y,grid):
    if method=='isotonic': return np.interp(grid,x,isotonic(y))
    a,b,t=exponential(x,y); return a+b*np.exp(-grid/t)

def crossing(grid,ys,threshold):
    if ys[0] < threshold: return '', 'not_met_at_4m'
    if ys[-1] >= threshold: return '', 'at_least_256m'
    idx=int(np.flatnonzero(ys<threshold)[0]); x0,x1=grid[idx-1:idx+1]; y0,y1=ys[idx-1:idx+1]
    return float(x0+(threshold-y0)*(x1-x0)/(y1-y0)),'within_range'

def save(name,header,rows):
    OUT.mkdir(parents=True,exist_ok=True)
    with (OUT/name).open('w',encoding='utf-8',newline='') as f:
        w=csv.writer(f,lineterminator='\n');w.writerow(header);w.writerows(rows)

def main():
    data=read_data(); ranges=[]; grids=[]; cv=[]; noise=[]
    missing={}
    with INPUT.open(encoding='utf-8',newline='') as f:
        for r in csv.DictReader(f):
            key=(r['call_type'],r['metric'],int(r['distance_m']))
            n,total=int(r['valid_n']),int(r['total_n']); avg=float(r['mean'])
            if not 0<n<=total: raise ValueError('invalid missingness count')
            missing[key]=(avg,avg) if n==total else (avg*n/total,(avg*n+total-n)/total)
    extreme=[]
    for call in CALLS:
        for d in DIST:
            lo=np.mean([missing[(call,m,int(d))][0] for m in METRICS])
            hi=np.mean([missing[(call,m,int(d))][1] for m in METRICS])
            extreme.append([call,int(d),float(lo),float(hi),'deterministic_extremes_not_confidence_interval'])
    grid=np.linspace(4,256,2521)
    for call in CALLS:
        for wname,weights in WEIGHTS.items():
            y=np.array(weights)@data[call]
            for method in ('isotonic','exponential'):
                curve=predict(method,DIST,y,grid)
                if np.any(curve < -1e-10) or np.any(curve>1+1e-10) or np.any(np.diff(curve)>1e-9):
                    raise ValueError('candidate prediction out of range or non-monotone')
                scenario=method+'_'+wname
                for th,state in LEVELS:
                    x,status=crossing(grid,curve,th)
                    ranges.append([call,scenario,th,state,x,'','',status,'not_estimable_from_aggregate','AI_candidate_unreviewed'])
                if wname=='equal':
                    for d in range(4,257):
                        grids.append([call,d,scenario,float(np.interp(d,grid,curve)),'','',wname,'not_estimable_from_aggregate','AI_candidate_unreviewed'])
                    for reduction in (0,.05,.10,.15,.20):
                        for th in (.5,.6,.7):
                            x,status=crossing(grid,curve*(1-reduction),th)
                            noise.append([call,method,reduction,th,x,status])
                    for i in range(1,6):
                        pred=predict(method,np.delete(DIST,i),np.delete(y,i),np.array([DIST[i]]))[0]
                        cv.append([call,method,int(DIST[i]),float(y[i]),float(pred),float(pred-y[i])])
    save('fidelity_grid.csv',['call_type','distance_m','scenario','estimate','lower','upper','weight_scheme','interval_method','review_status'],grids)
    save('communication_ranges.csv',['call_type','scenario','threshold','recognition_state','radius_m','lower','upper','status','interval_method','review_status'],ranges)
    save('candidate_distance_cv.csv',['call_type','model','held_out_distance_m','observed','prediction','residual'],cv)
    save('noise_scenarios.csv',['call_type','model','relative_reduction','threshold','radius_m','status'],noise)
    save('missingness_extremes.csv',['call_type','distance_m','min_if_missing_zero','max_if_missing_one','interpretation'],extreme)
    meta={'run_id':'q2_candidates_v1','status':'AI-generated exploratory candidate; not team-approved',
          'input_sha256':hashlib.sha256(INPUT.read_bytes()).hexdigest(),
          'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'python':platform.python_version(),'numpy':np.__version__,'cleaning_version':'q2_1_v1',
          'distance_domain_m':[4,256],'tau_grid':[4,2048,400],
          'weights':WEIGHTS,'thresholds':LEVELS,'random_seed':None,
          'intervals':'unavailable; original recording dependencies not identifiable from tables'}
    (OUT/'candidate_metadata.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
    report=ROOT/'experiments/reports'; report.mkdir(parents=True,exist_ok=True)
    with (report/'q2_candidate_ranges_summary.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.writer(f,lineterminator='\n')
        w.writerow(['call_type','scenario','threshold','recognition_state','radius_m','status','interval_method','review_status'])
        for r in ranges:
            if r[1].endswith('_equal'):w.writerow([r[0],r[1],r[2],r[3],r[4],r[7],r[8],r[9]])
    with (report/'q2_candidate_weight_sensitivity.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.writer(f,lineterminator='\n'); w.writerow(['call_type','scenario','threshold','recognition_state','radius_m','status','interval_method','review_status'])
        for r in ranges:w.writerow([r[0],r[1],r[2],r[3],r[4],r[7],r[8],r[9]])
    with (report/'q2_candidate_noise_sensitivity.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.writer(f,lineterminator='\n');w.writerow(['call_type','model','relative_reduction','threshold','radius_m','status']);w.writerows(noise)
    with (report/'q2_candidate_cv_summary.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.writer(f,lineterminator='\n'); w.writerow(['call_type','model','held_out_interior_levels','mae','rmse'])
        for call in CALLS:
            for method in ('isotonic','exponential'):
                errors=np.array([r[-1] for r in cv if r[0]==call and r[1]==method])
                w.writerow([call,method,len(errors),float(np.mean(abs(errors))),float(np.sqrt(np.mean(errors**2)))])
    with (report/'q2_missingness_extremes.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.writer(f,lineterminator='\n');w.writerow(['call_type','distance_m','min_if_missing_zero','max_if_missing_one','interpretation']);w.writerows(extreme)
    (report/'q2_candidate_metadata.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
    print('Generated candidate grids, ranges, CV and scenarios under results/q2.')

if __name__=='__main__':main()
