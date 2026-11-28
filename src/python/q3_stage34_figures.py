"""Descriptive figures from saved OOF predictions; does not fit or select models."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from q3_playback_analysis import ROOT, plt
import numpy as np
import pandas as pd


def main(counts,latency):
    out=ROOT/'figures/q3'/datetime.now(timezone.utc).strftime('q3_stage34_%Y%m%dT%H%M%SZ')
    out.mkdir(parents=True,exist_ok=False)
    c=pd.read_csv(ROOT/counts/'calibration.csv')
    fig,ax=plt.subplots(figsize=(5.5,4))
    for family in ['poisson','nb2']:
        s=c[(c.route=='expID')&(c.model==f'hurdle_{family}_full')]
        ax.plot(s.predicted_mean,s.observed_mean,'o-',label=f'Hurdle {family.upper()}')
    top=max(c.predicted_mean.max(),c.observed_mean.max())*1.05
    ax.plot([0,top],[0,top],'k--',linewidth=1,label='Identity')
    ax.set(xlabel='Mean OOF predicted count',ylabel='Observed mean count',title='Count calibration by prediction quintile')
    ax.legend();fig.tight_layout();fig.savefig(out/'count_calibration.png',dpi=220);plt.close(fig)
    o=pd.read_csv(ROOT/latency/'latency_oof.csv');times=[1,5,10,30,60]
    fig,axes=plt.subplots(1,3,figsize=(12,3.8),sharey=True)
    for ax,b in zip(axes,['HeadsUp','Vocal','Approach']):
        base=o[(o.route=='expID')&(o.behavior==b)&(o.version=='exclude_conflicts')]
        s=base[base.model=='window_lognormal_type']
        observed=[np.mean((s.actual_event==1)&(s.actual_latency_s<=t)) for t in times]
        ax.plot(times,observed,'ko-',label='Observed')
        for model,label in [('window_lognormal_type','Window log-normal'),('window_weibull_type','Window Weibull'),('aft_lognormal_type','AFT log-normal')]:
            sub=base[base.model==model]
            ax.plot(times,[sub[f'cdf_{t}s'].mean() for t in times],'.--',label=label)
        ax.set(title=f'{b}: n={len(s)}, events={int(s.actual_event.sum())}',xlabel='Time after playback (s)')
        ax.set_ylim(0,.36);ax.grid(alpha=.2)
    axes[0].set_ylabel('Population probability of response by t')
    axes[-1].legend(fontsize=8);fig.tight_layout();fig.savefig(out/'latency_cumulative_calibration.png',dpi=220);plt.close(fig)
    (out/'metadata.json').write_text(json.dumps(dict(count_run=str(counts),latency_run=str(latency),
        scope='pooled expID OOF predictions; descriptive calibration; no intervals or model selection'),indent=2),encoding='utf-8')
    print(out)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--counts',required=True,type=Path)
    parser.add_argument('--latency',required=True,type=Path);args=parser.parse_args()
    main(args.counts,args.latency)
