"""R2-1 population/pair/support audit only: no model fitting or recoding."""
import json,hashlib
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
import pandas as pd
from q3_playback_analysis import ROOT,INPUT,COLS
from q3_revised_models import support


def run():
    d=pd.read_csv(INPUT);d['source_row_id']=d.index+1
    assert d.groupby('expID').size().eq(2).all()
    p=d[d.Type=='call'].merge(d[d.Type=='control'],on='expID',suffixes=('_call','_control'),validate='one_to_one')
    assert len(p)==139 and p.CallType_control.eq('control').all()
    stamp=datetime.now(timezone.utc).strftime('r2_%Y%m%dT%H%M%SZ');out=ROOT/'results/q3/round2'/stamp/'R2_1';out.mkdir(parents=True)
    p.to_csv(out/'pair_mapping.csv',index=False)
    masks={'pattern':np.ones(len(d),bool),'count':np.ones(len(d),bool)}
    for b in ['HeadsUp','Vocal','Approach']:
        masks['latency_'+b]=~((d[b+'YesNo']==0)&d[b+'Latency'].notna())
    for b in ['HeadsUp','Approach']:
        masks['duration_record_'+b]=masks['latency_'+b]&~(d[b+'Latency']+d[b+'Duration']>60)
    membership=[];audits=[];refs=[];poprows=[]
    for module,mask in masks.items():
        pop=d.loc[mask];ids=set(pop.source_row_id)
        for i in pop.source_row_id:membership.append(dict(module=module,source_row_id=i))
        if module=='pattern':event=pop.ResponseYesNo
        elif module=='count':event=pop.VocalNcalls>0
        else:
            b=module.split('_')[-1];event=pop[b+'YesNo'] if module.startswith('latency') else pop[b+'Duration']>0
        for typ in ['flat','mod','tv']:
            pairs=p[p.CallType_call==typ];complete=0;kept=[]
            for _,pair in pairs.iterrows():
                eligible=pair.source_row_id_call in ids and pair.source_row_id_control in ids
                labels=[]
                for side in ['call','control']:
                    x=np.array([pair[c+'_'+side] for c in COLS[2:]],float)
                    for stimulus in [typ,'control']:
                        cell=pop[(pop.CallType==stimulus)&(pop.Context==pair['Context_'+side])]
                        labels.append(support(cell[COLS[2:]].to_numpy(float),x))
                ok=eligible and all(s in ['interpolation','boundary'] for s in labels)
                complete+=eligible
                audits.append(dict(module=module,call_type=typ,exp_id=pair.expID,
                    complete_evaluable_pair=eligible,call_x_in_call=labels[0],call_x_in_control=labels[1],
                    control_x_in_call=labels[2],control_x_in_control=labels[3],adjusted_pair_retained=ok,
                    reason='retained' if ok else 'unevaluable_side' if not eligible else 'outside_or_unverified_joint_support'))
                if ok:kept.append(pair)
            for pair in kept:
                for side in ['call','control']:
                    row=dict(module=module,comparison_id=f'{module}_{typ}_paired_supported',call_type=typ,
                        exp_id=pair.expID,reference_side=side,source_row_id=pair['source_row_id_'+side],
                        context=pair['Context_'+side],weight=1/(2*len(kept)),
                        reference_scope='fixed_observed_supported_pairs',bootstrap_scope='conditional_on_fixed_reference_population')
                    row.update({c:pair[c+'_'+side] for c in COLS[2:]});refs.append(row)
            selected=p[p.expID.isin([x.expID for x in kept])]
            selected_ids=set(selected.source_row_id_call)|set(selected.source_row_id_control)
            selected_pop=pop[pop.source_row_id.isin(selected_ids)]
            if module=='pattern':n_event=int(selected_pop.ResponseYesNo.sum())
            elif module=='count':n_event=int((selected_pop.VocalNcalls>0).sum())
            elif module.startswith('latency'):n_event=int(selected_pop[module.split('_')[-1]+'YesNo'].sum())
            else:n_event=int((selected_pop[module.split('_')[-1]+'Duration']>0).sum())
            poprows.append(dict(module=module,call_type=typ,model_population_n=len(pop),model_event_n=int(event.sum()),
                raw_pair_n=len(pairs),complete_pair_n=int(complete),supported_pair_n=len(kept),supported_row_n=2*len(kept),
                supported_track_n=selected.PlaybackTrack_call.nunique(),supported_date_n=selected.Date_call.nunique(),
                supported_event_n=n_event,formal_duration_ready=False if module.startswith('duration') else None,
                adjusted_comparison='not_estimable_empty_support' if not kept else 'estimable_model_association_check_sparse_support'))
    pd.DataFrame(poprows).to_csv(out/'analysis_populations.csv',index=False)
    pd.DataFrame(membership).to_csv(out/'analysis_membership.csv',index=False)
    pd.DataFrame(audits).to_csv(out/'support_audit.csv',index=False)
    ref=pd.DataFrame(refs);ref.to_csv(out/'comparison_reference.csv',index=False)
    if len(ref):assert np.allclose(ref.groupby('comparison_id').weight.sum(),1)
    inventory=[]
    for stage,runid,file,groups in [('S2','q3_stage2_20261127T115748Z','oof_combinations.csv',['model']),
        ('S2_GEE','q3_stage2_20261127T115748Z','gee_oof_predictions.csv',['model']),
        ('S3','q3_stage3_20261127T125020Z','count_oof.csv',['model']),
        ('S4','q3_stage4_20261127T125945Z','latency_oof.csv',['version','behavior','model']),
        ('S5','q3_stage5_20261127T131905Z','duration_oof.csv',['behavior','model'])]:
        source=ROOT/'results/q3'/runid/file;t=pd.read_csv(source)
        for key,z in t.groupby(groups):
            if not isinstance(key,tuple):key=(key,)
            for route,part in z.groupby('route') if 'route' in z else [('expID',z)]:
                inventory.append(dict(stage=stage,component='|'.join(map(str,key)),route=route,n=len(part),
                    unique_source_rows=part.source_row_id.nunique(),source=str(source.relative_to(ROOT)),
                    reuse='existing_OOF_only_no_new_reference_predictions'))
    pd.DataFrame(inventory).to_csv(out/'existing_evidence_inventory.csv',index=False)
    evidence='''# R2-1 设计与未决语义

来源：[原研究 Playback experiment](https://ore.eu/article/view/1538/version/2510)，本轮核对方法段。
论文明确说明同一群体播放 call/control、交替随机顺序，轨道在情境内不放回随机抽取；对照为海浪声，不是静默。记录了群体间隔离安排。这是设计支持，不能继续写成文献完全未说明随机化。
CSV 没有逐对播放顺序、两次播放间隔或个体身份字段，不能检查实际遵循情况、组内残留效应及跨实验重复身份。Distance、Context、Npenguins 不是据此已随机分配；仍以调整关联为主，不自动升级全部比较为因果效应。
论文方法记 flat/mod/tv 轨道数9/7/10，CSV自然轨道标识11/7/10，操作性28不改；底层录音映射未明，原型与样本/版本差异应保留。不能将不同标识直接当独立个体。
Duration=60、V4/A5冲突与H9零点没有获得新增编码依据，沿用第一轮未决处理。没有改写值或自动联系作者。
主调整参考人口固定为支持筛查后原观测配对，每对等权、两侧半权；区间对该固定参考人口条件化。参考人口抽样变异如另研究，应另名报告。支持标准沿用SVD退化维度凸包，数值容差1e-7，不是测量精度。
共同支持为空不估调整主对比；支持非空但小样本保留数量/限制，不新增事后阈值。原始全配对描述仍可做；外推敏感性与统一人口补充不得冒充主比较。
S6只保存36个预定格点的Bootstrap预测及少量形状参数，没有全部重复的回归系数；一般不能恢复本轮观测配对参考点预测。新参考区间需要必要的固定模型重拟合/重预测，不能相减旧区间端点。日期结果以清单为准，GEE与额外Latency口径未有日期OOF。
'''
    (out/'design_and_semantics_evidence.md').write_text(evidence,encoding='utf-8')
    meta=dict(run_id=stamp,input_sha256=hashlib.sha256(INPUT.read_bytes()).hexdigest(),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),support_tolerance=1e-7,
        old_support_helper_sha256=hashlib.sha256((ROOT/'src/python/q3_revised_models.py').read_bytes()).hexdigest(),
        models_fitted=False,adjusted_outcomes_computed=False,formal_duration_ready=False,
        source_protocol='https://ore.eu/article/view/1538/version/2510',
        comparison_definitions=dict(observed='actual matched observations; conditions may differ',
          adjusted='same-x call/control model contrast; equal pairs and half weight per side',
          supplementary='separate explicitly defined common population; not main matched target'),
        acceptance=dict(pair_mapping=True,source_rows=int(len(d)),support_pairs_atomic=True,reference_weights_sum1=True))
    (out/'metadata.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    (out/'implementation_snapshot.py').write_bytes(Path(__file__).read_bytes())
    print(out);print(pd.DataFrame(poprows)[['module','call_type','model_population_n','complete_pair_n','supported_pair_n']].to_string(index=False))


if __name__=='__main__':run()
