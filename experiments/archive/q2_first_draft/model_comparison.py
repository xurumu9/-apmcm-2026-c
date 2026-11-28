"""Compare linear- and log-distance interpolation using held-out distance levels."""
from pathlib import Path
import csv
import numpy as np
import analyze as a

def model_predict(x,y,d,method):
 z=np.asarray(x,dtype=float); d=float(d)
 if not z[0]<=d<=z[-1]: raise ValueError('Cannot extrapolate')
 return float(np.interp(np.log(d) if method=='log_distance' else d,
                        np.log(z) if method=='log_distance' else z,y))

def crossing(y,t,method):
 if y[0]<t:return None,'below_at_4m'
 for i in range(1,len(a.DIST)):
  if y[i]<t:
   p=(t-y[i-1])/(y[i]-y[i-1]); d0,d1=a.DIST[i-1:i+1]
   return (float(np.exp(np.log(d0)+p*(np.log(d1)-np.log(d0)))) if method=='log_distance'
           else float(d0+p*(d1-d0))),'within_range'
 return None,'at_least_256m'

def main():
 data=a.load(); cv=[]; scenarios=[]
 for call in a.CALLS:
  m=np.array([[data[(call,f,int(d))][0].mean() for d in a.DIST] for f in a.FEATURES])
  y=np.mean(m,axis=0)
  for method in ['linear_distance','log_distance']:
   for i in range(1,len(a.DIST)-1):
    pred=model_predict(np.delete(a.DIST,i),np.delete(y,i),a.DIST[i],method)
    cv.append([call,method,int(a.DIST[i]),y[i],pred,pred-y[i]])
   for name,weights in a.WEIGHTS.items():
    vals=np.asarray(weights)@m
    for t in a.THRESHOLDS:
     v,status=crossing(vals,t,method)
     scenarios.append([call,method,name,t,status,'' if v is None else v])
 a.save('06_model_validation.csv',['call','method','held_out_distance_m','observed_composite','predicted_composite','error'],cv)
 a.save('07_model_weight_scenarios.csv',['call','method','weights','threshold','status','first_crossing_m'],scenarios)
 summary=[]
 for call in a.CALLS:
  for method in ['linear_distance','log_distance']:
   rs=[r for r in cv if r[0]==call and r[1]==method]
   summary.append([call,method,len(rs),np.mean([abs(r[-1]) for r in rs]),np.sqrt(np.mean([r[-1]**2 for r in rs]))])
 a.save('08_cv_summary.csv',['call','method','held_out_interior_levels','mae','rmse'],summary)
 ranges=[]
 for call in a.CALLS:
  for t in a.THRESHOLDS:
   rows=[r for r in scenarios if r[0]==call and r[3]==t]
   values=[r[5] for r in rows if r[4]=='within_range']
   ranges.append([call,t,min(values) if values else '',max(values) if values else '',len(values),sum(r[4]=='below_at_4m' for r in rows),sum(r[4]=='at_least_256m' for r in rows)])
 a.save('09_scenario_ranges.csv',['call','threshold','min_crossing_m','max_crossing_m','within_range_count','below_at_4m_count','at_least_256m_count'],ranges)
 print('CV summaries:',summary)
 print('Model/weight scenario ranges:',ranges)

if __name__=='__main__':main()
