"""Reproduce descriptive analysis and sensitivity scenarios (Python 3, numpy, Pillow)."""
from pathlib import Path
import csv, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data'
OUT=ROOT/'results'
OUT.mkdir(exist_ok=True)
DIST=np.array([4.,8.,16.,32.,64.,128.,256.])
CALLS=['flat','mod','tv']
FEATURES=['spectrogram','amplitude_spectrum','envelope']
FILES={
 'flat':[3,6,9], 'mod':[4,7,10], 'tv':[5,8,11]
}
WEIGHTS={'equal':(1/3,1/3,1/3), 'spectrogram_priority':(.6,.2,.2),
         'spectrum_priority':(.2,.6,.2),'envelope_priority':(.2,.2,.6)}
THRESHOLDS=[.5,.6,.7]

def save(name,header,rows):
 with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.writer(f); w.writerow(header); w.writerows(rows)

def load():
 result={}
 for call,ids in FILES.items():
  for feature,num in zip(FEATURES,ids):
   files=list(DATA.glob(f'Data{num:02d}_*.csv'))
   if len(files)!=1: raise RuntimeError(f'Expected exactly one Data{num:02d} file')
   with files[0].open(encoding='utf-8-sig',newline='') as f:
    reader=csv.DictReader(f)
    expected=[f'{int(d)}m' for d in DIST]
    if reader.fieldnames!=expected: raise ValueError(f'Unexpected columns: {reader.fieldnames}')
    rows=list(reader)
   for d,label in zip(DIST,expected):
    vals=np.array([float(row[label]) for row in rows if row[label].strip().upper() not in ('','NA','NAN')])
    if not len(vals) or np.any((vals < -1)|(vals > 1)): raise ValueError('Invalid correlations')
    result[(call,feature,int(d))]=(vals,len(rows))
 return result

def first_cross(values,threshold):
 """First decline below threshold starting at 4m, linear in distance; never extrapolate."""
 if values[0]<threshold: return None,'below_at_4m'
 for i in range(1,len(DIST)):
  if values[i]<threshold:
   x=DIST[i-1]+(threshold-values[i-1])*(DIST[i]-DIST[i-1])/(values[i]-values[i-1])
   return float(x),'within_range'
 return None,'at_least_256m'

def crossings(values,threshold):
 xs=[]
 for i in range(1,len(DIST)):
  if (values[i-1]-threshold)*(values[i]-threshold)<0:
   xs.append(float(DIST[i-1]+(threshold-values[i-1])*(DIST[i]-DIST[i-1])/(values[i]-values[i-1])))
 return xs

def predict(call,distance,weight='equal'):
 """Returns a modelled mean similarity only for 4–256 m, not response probability."""
 if distance<4 or distance>256: raise ValueError('Distance outside observed range 4–256 m')
 obs=load()
 means=np.array([[obs[(call,f,int(d))][0].mean() for d in DIST] for f in FEATURES])
 return float(np.interp(distance,DIST,np.array(WEIGHTS[weight])@means))

def chart(call,means,sd,combined):
 W,H=1300,900; im=Image.new('RGB',(W,H),'white'); draw=ImageDraw.Draw(im)
 try:
  font=ImageFont.truetype('arial.ttf',23); small=ImageFont.truetype('arial.ttf',19); title=ImageFont.truetype('arial.ttf',32)
 except OSError: font=small=title=ImageFont.load_default()
 L,R,T,B=105,1225,95,685
 xx=lambda x: L+(x-4)/(256-4)*(R-L)
 yy=lambda y: B-y*(B-T)
 for y in np.arange(0,1.01,.2):
  py=yy(y); draw.line((L,py,R,py),fill='#e1e7ec',width=1); draw.text((40,py-12),f'{y:.1f}',font=small,fill='#333333')
 for i,d in enumerate(DIST):
  x=xx(d); draw.line((x,T,x,B),fill='#edf0f3'); draw.text((x-7,B+14+(22 if i==1 else 0)),str(int(d)),font=small,fill='#333333')
 draw.line((L,T,L,B,R,B),fill='#333333',width=2)
 colors=['#1769aa','#e08724','#9a4a8a','#128268']
 names=['Spectrogram','Amplitude spectrum','Amplitude envelope','Composite (equal weights)']
 for j,series in enumerate(list(means)+[combined]):
  pts=[(xx(d),yy(v)) for d,v in zip(DIST,series)]; draw.line(pts,fill=colors[j],width=4)
  for i,(x,y) in enumerate(pts):
   if j<3: draw.line((x,yy(max(0,series[i]-sd[j,i])),x,yy(min(1,series[i]+sd[j,i]))),fill=colors[j],width=1)
   draw.ellipse((x-5,y-5,x+5,y+5),fill=colors[j])
  lx=125+(j%2)*540; ly=795+(j//2)*32
  draw.line((lx,ly+10,lx+36,ly+10),fill=colors[j],width=4); draw.text((lx+45,ly),names[j],font=small,fill='#222222')
 draw.text((L,24),f'{call}: correlation with 1 m reference',font=title,fill='#172c3c')
 draw.text((L,53),'Points = means; thin bars = +/- 1 SD; lines interpolate between observed distances',font=small,fill='#4d5961')
 draw.text((530,750),'Distance (m)',font=font,fill='#222222')
 im.save(OUT/f'{call}_correlations.png')

def main():
 data=load()
 stats=[]; combined_rows=[]; sensitivity=[]; thresholds=[]; noise=[]
 for call in CALLS:
  means=np.array([[data[(call,f,int(d))][0].mean() for d in DIST] for f in FEATURES])
  std=np.array([[data[(call,f,int(d))][0].std(ddof=1) for d in DIST] for f in FEATURES])
  for j,f in enumerate(FEATURES):
   for i,d in enumerate(DIST):
    a,total=data[(call,f,int(d))]; stats.append([call,f,int(d),total,len(a),total-len(a),means[j,i],std[j,i],a.min(),a.max()])
  equal=np.array(WEIGHTS['equal'])@means
  chart(call,means,std,equal)
  for i,d in enumerate(DIST): combined_rows.append([call,int(d),*means[:,i],equal[i]])
  for th in THRESHOLDS:
   x,status=first_cross(equal,th); cross=crossings(equal,th)
   thresholds.append([call,th,status,x if x is not None else '', '; '.join(f'{a:.2f}' for a in cross)])
   for name,weights in WEIGHTS.items():
    vals=np.array(weights)@means; v,s=first_cross(vals,th)
    sensitivity.append([call,th,name,*weights,s,'' if v is None else v,'; '.join(f'{z:.2f}' for z in crossings(vals,th))])
   for reduction in [0,.05,.10,.20]:
    v,s=first_cross(equal*(1-reduction),th)
    noise.append([call,th,reduction,s,'' if v is None else v])
 save('01_descriptive.csv',['call','feature','distance_m','total_rows','valid_n','missing_n','mean','sd','min','max'],stats)
 save('02_composite_observed.csv',['call','distance_m','spectrogram_mean','spectrum_mean','envelope_mean','equal_weight_fidelity'],combined_rows)
 save('03_threshold_crossings.csv',['call','threshold','status','first_crossing_m','all_crossings_m'],thresholds)
 save('04_weight_sensitivity.csv',['call','threshold','weight_scenario','w_spectrogram','w_spectrum','w_envelope','status','first_crossing_m','all_crossings_m'],sensitivity)
 save('05_noise_scenarios.csv',['call','threshold','relative_reduction','status','first_crossing_m'],noise)
 print('Completed:',OUT)
 for row in thresholds: print(row)

if __name__=='__main__': main()
