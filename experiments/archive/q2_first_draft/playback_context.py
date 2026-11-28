"""Descriptive paired playback context; not a causal or recognition-threshold model."""
from pathlib import Path
from collections import defaultdict
import csv
import analyze as a

def main():
 files=list(a.DATA.glob('Data02_*.csv'))
 if len(files)!=1: raise RuntimeError('Missing Data02')
 with files[0].open(encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
 groups=defaultdict(list)
 for row in rows: groups[row['expID']].append(row)
 accum=defaultdict(list)
 for exp,pair in groups.items():
  if len(pair)!=2 or {r['Type'] for r in pair}!={'call','control'}:raise ValueError('Unexpected pair '+exp)
  call=next(r for r in pair if r['Type']=='call'); control=next(r for r in pair if r['Type']=='control')
  if call['Context']!=control['Context']:raise ValueError(f'Pair {exp} mismatch in Context')
  d=float(call['Distance']); band='5-49m' if d<50 else ('50-99m' if d<100 else '100-200m')
  accum[(call['CallType'],band)].append((int(call['ResponseYesNo']),int(control['ResponseYesNo']),float(control['Distance'])!=d,call['Npenguins']!=control['Npenguins']))
 out=[]
 for (call,band),arr in sorted(accum.items()):
  n=len(arr); natural=sum(r[0] for r in arr); control=sum(r[1] for r in arr)
  out.append([call,band,n,natural,control,natural/n,control/n,(natural-control)/n,sum(r[2] for r in arr),sum(r[3] for r in arr)])
 a.save('10_paired_playback_context.csv',['call_type','natural_call_distance_band','paired_experiments','natural_responses','control_responses','natural_rate','control_rate','paired_rate_difference','distance_mismatch_count','group_size_mismatch_count'],out)
 print('Pairs',len(groups),'results',out)

if __name__=='__main__':main()
