"""R2-6 integration/acceptance only; no fitting or raw-data mutation."""
import json
import hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from q3_playback_analysis import ROOT,INPUT
from q3_round2_pattern import FOUNDATION,UNITS,FIELDS as PATTERN_FIELDS

OUT=FOUNDATION.parent/'R2_6'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    OUT.mkdir(parents=True,exist_ok=False);run=FOUNDATION.parent;combined=[];manifest=[]
    definitions=[('Pattern','R2_2/pattern_adjusted_contrasts.csv','probability_difference','outcome','original_HVA_flags','all278', 'probability'),
        ('Intensity','R2_3/count_paired_contrasts.csv','difference','estimand','actual_count_positive','all278_actual_count','calls_or_probability'),
        ('Latency','R2_4/latency_window_probability_contrasts.csv','difference','estimand','behavior_flag_exclude_semantic_conflicts','H278_V274_A273','probability'),
        ('Latency_conditional','R2_4/latency_conditional_time_contrasts.csv','difference','estimand','behavior_flag_exclude_semantic_conflicts','H278_V274_A273','seconds_or_cumulative_probability')]
    for module,rel,estimate,target,event,pop,unit in definitions:
        source=run/rel;z=pd.read_csv(source)
        for _,r in z.iterrows():
            is_a=module=='Latency_conditional' and r.get('behavior')=='Approach' and r[target] in ['conditional_median_s','conditional_mean_s','positive_median_s','positive_mean_s']
            combined.append(dict(module=module,call_type=r.call_type,behavior=r.get('behavior',''),estimand=r[target],estimate=r[estimate],lower=r.lower,upper=r.upper,
                unit=('probability' if module=='Pattern' or r[target] in ['q_positive','p_response'] or str(r[target]).startswith('cdf_') else 'calls_per_group_playback' if module=='Intensity' else 'seconds'),
                primary_comparison=(r[target]=='any' if module=='Pattern' else r[target]=='mean_total' if module=='Intensity' else module=='Latency'),
                reference_pair_n=r.reference_pair_n,resampling_unit=r.resampling_unit,bootstrap_success_n=r.bootstrap_success_n,bootstrap_total_n=r.bootstrap_total_n,
                comparison_population='type_specific_fixed_supported_matched_pairs_equal_pairs_half_sides',
                observation_window_s=60,event_definition=event,model_population=pop,
                evidence_level='borrowed_control_time_no_direct_response_evidence' if is_a else 'exploratory_adjusted_association',
                q4_use='sensitivity_only_not_validated_control_time' if is_a else 'conditional_model_input_with_population_and_support_limits',
                shared_probability=(module=='Latency' and r.get('behavior')=='HeadsUp'),
                interval_kind='pointwise95_parameter_confidence_not_future_prediction_fixed_model_and_reference',source=str(source.relative_to(ROOT))))
        manifest.append(dict(module=module,path=str(source.relative_to(ROOT)),sha256=sha(source),target=event,
            population=pop,reference='type_specific_fixed_supported_matched_pairs',unit=unit,
            uncertainty='expID_primary_natural_track_separate_sensitivity_500_each_fixed_model_not_selection',use='preserve_behavior_event_population_and_reference_labels'))
    table=pd.DataFrame(combined);table.to_csv(OUT/'unified_scientific_conclusions.csv',index=False)
    old=ROOT/'results/q3/q3_stage6_full_20261127T133654Z'
    for f in ['combination_predictions.csv','latency_intensity_predictions.csv','representative_call_control_contrasts.csv','future_experiment_prediction_intervals.csv','combination_future_prediction_sets.csv','bootstrap_expID.npz','bootstrap_natural_track.npz']:
        manifest.append(dict(module='S6_36_scenarios',path=str((old/f).relative_to(ROOT)),sha256=sha(old/f),target='as_labelled_in_original_file',
            population='as_labelled_in_original_S6',reference='fixed_36_scenarios_not_new_matched_population',unit='preserve_original_unit',
            uncertainty='fixed_model_S6_not_new_reference_intervals',use='unchanged_legacy_interface_keep_support_extrapolation_and_availability_labels'))
    manifest.append(dict(module='Duration',path=str((run/'R2_3/duration_identifiability.md').relative_to(ROOT)),sha256=sha(run/'R2_3/duration_identifiability.md'),
        target='true_behavior_duration',population='unresolved_observation_mechanism',reference='not_identified',unit='seconds',uncertainty='not_estimated',use='no_formal_numeric_input'))
    pd.DataFrame(manifest).to_csv(OUT/'q4_input_manifest.csv',index=False)
    checks={}
    archive=pd.read_csv(ROOT/'file_manifest.csv')
    assert all(sha(ROOT/r.Destination.replace('\\','/')).lower()==r.SHA256.lower() for _,r in archive.iterrows());checks['original_archive_hashes']=len(archive)
    om=json.loads((old/'metadata.json').read_text())
    assert all(sha(ROOT/'src/python'/name)==h for name,h in om['helper_sha256'].items());checks['first_round_helpers_unchanged']=True
    pairs=pd.read_csv(FOUNDATION/'pair_mapping.csv');assert len(pairs)==139 and pairs.expID.is_unique
    assert set(pairs.source_row_id_call)|set(pairs.source_row_id_control)==set(range(1,279));checks['source_pair_coverage']=True
    ref=pd.read_csv(FOUNDATION/'comparison_reference.csv');assert np.allclose(ref.groupby('comparison_id').weight.sum(),1);assert ref.groupby(['comparison_id','exp_id']).size().eq(2).all();checks['reference_weights_and_atomic_pairs']=True
    for u in UNITS:
        p=np.load(run/'R2_2'/f'pattern_bootstrap_{u}.npz')['adjusted']
        assert np.allclose(p[:,:,:,4:].sum(-1),1) and np.allclose(p[:,:,:,0],1-p[:,:,:,4])
        l=np.load(run/'R2_4'/f'latency_bootstrap_{u}.npz')['estimate'];assert np.allclose(p[:,:,:,1],l[:,0,:,:,0],equal_nan=True)
        for module,file,key,fields,shape in [
            ('R2_2','pattern_adjusted_contrasts.csv','adjusted',PATTERN_FIELDS,(3,2,12)),
            ('R2_3','count_paired_contrasts.csv','estimate',['q_positive','mean_positive','mean_total'],(3,2,3))]:
            prefix='pattern' if module=='R2_2' else 'count';a=np.load(run/module/f'{prefix}_bootstrap_{u}.npz')[key]
            assert a.shape[1:]==shape
            z=pd.read_csv(run/module/file);z=z[z.resampling_unit==u]
            for j,t in enumerate(['flat','mod','tv']):
                for k,f in enumerate(fields):
                    s=z[(z.call_type==t)&(z['outcome' if module=='R2_2' else 'estimand']==f)].iloc[0];delta=a[:,j,0,k]-a[:,j,1,k];delta=delta[np.isfinite(delta)]
                    assert np.allclose([s.lower,s.upper],np.quantile(delta,[.025,.975]))
        fields=['p_response','conditional_median_s','conditional_mean_s','positive_median_s','positive_mean_s','cdf_1s','cdf_5s','cdf_10s','cdf_30s','cdf_60s']
        z=pd.concat([pd.read_csv(run/'R2_4'/f) for f in ['latency_window_probability_contrasts.csv','latency_conditional_time_contrasts.csv']]);z=z[z.resampling_unit==u]
        for j,b in enumerate(['HeadsUp','Vocal','Approach']):
            for k,t in enumerate(['flat','mod','tv']):
                for m,f in enumerate(fields):
                    s=z[(z.behavior==b)&(z.call_type==t)&(z.estimand==f)].iloc[0];delta=l[:,j,k,0,m]-l[:,j,k,1,m];delta=delta[np.isfinite(delta)]
                    assert np.allclose([s.lower,s.upper],np.quantile(delta,[.025,.975]))
    checks['saved_joint_vectors_and_all_interval_recalculations']=True;checks['H_shared_same_replicates']=True
    s=pd.read_csv(run/'R2_4/latency_oof_score_decomposition.csv');assert np.allclose(s.gate_mean_nll+s.atom_mean_nll+s.density_mean_nll,s.joint_mean_nll);checks['latency_score_decomposition']=True
    s=pd.read_csv(run/'R2_3/count_component_diagnostics.csv');assert np.allclose(s.gate_weighted_error+s.positive_weighted_error,s.total_error);checks['count_error_decomposition']=True
    checks['formal_duration_ready']=False;checks['scientific_validity_proven_by_software']=False
    (OUT/'acceptance.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
    (OUT/'metadata.json').write_text(json.dumps(dict(stage='R2-6',input_sha256=sha(INPUT),script_sha256=sha(Path(__file__)),models_rerun=False,
        formal_duration_ready=False,source_run=str(run.relative_to(ROOT)),inherited_environment='R2_2/metadata.json'),indent=2),encoding='utf-8')
    (OUT/'implementation_snapshot.py').write_bytes(Path(__file__).read_bytes());print(json.dumps(checks,indent=2));print('Q4 manifest rows',len(manifest),'conclusion rows',len(table))


if __name__=='__main__':run()
