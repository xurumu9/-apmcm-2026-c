"""Build aggregate-only Q3 review delivery from an existing accepted final run.

No models, raw-data rows, per-record predictions or Bootstrap arrays published.
Source artifacts remain byte-for-byte unchanged. Run once per new output folder.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
from q3_delivery import ROOT,RELEASE,digest


def readcsv(p):
    with p.open(encoding='utf-8',newline='') as f:
        reader=csv.DictReader(f);return reader.fieldnames,list(reader)


def writecsv(p,fields,rows):
    with p.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore',lineterminator='\n');w.writeheader();w.writerows(rows)


def build(source,dest):
    source=Path(source).resolve();dest=Path(dest).resolve()
    if not source.is_relative_to(ROOT/'results/q3/final_revision'):raise ValueError('Source must be an existing final_revision run')
    if not dest.is_relative_to(ROOT/'experiments/reports'):raise ValueError('Delivery must stay under experiments/reports')
    acceptance=json.loads((source/'final_acceptance.json').read_text(encoding='utf-8'))
    if not acceptance['numerical_interface_pass']:raise ValueError('Final source has not passed numerical/interface acceptance')
    dest.mkdir(parents=True,exist_ok=False);provenance=[]
    selections={
      'q4_latency_original_flags_36.csv':['grid_row','call_type','context','distance_m','n_penguins','vocal_ncalls_before','behavior','estimand','estimate','lower','upper','unit','resampling_unit','bootstrap_success_n','bootstrap_total_n','joint_support','positive_time_type_n','positive_time_context_type_n','positive_time_evidence','conditional_time_joint_support','availability','conditional_time_information_required','cdf_semantics','within_HVA_probability_coherence_pass','common_joint_count_pattern_distribution_available'],
      'q4_combination_original_flags_36.csv':['grid_row','call_type','context','distance_m','n_penguins','vocal_ncalls_before','combo','probability','lower','upper','resampling_unit','bootstrap_success_n','bootstrap_total_n','joint_support','effective_n','event_n','event_definition','zero_state_semantics','model_population_n','constraints_pass','common_joint_count_pattern_distribution_available'],
      'q4_count_reused_36.csv':['grid_row','call_type','context','distance_m','n_penguins','vocal_ncalls_before','estimand','estimate','lower','upper','unit','resampling_unit','bootstrap_success_n','bootstrap_total_n','joint_support','conditional_joint_support','count_event_definition','p_V_pattern','q_count_positive','p_increase_from_NB2','p_V_minus_q','constraints_pass','common_joint_count_pattern_distribution_available'],
    }
    for name,fields in selections.items():
        original,rows=readcsv(source/name);assert set(fields)<=set(original),(name,set(fields)-set(original))
        writecsv(dest/name,fields,rows)
        provenance.append(dict(path=name,source=str((source/name).relative_to(ROOT).as_posix()),source_sha256=digest(source/name),transform='column_selection_only_numeric_lexemes_unchanged',rows=len(rows)))
    for name in ['latency_original_flags_paired.csv','q4_duration_unavailable.csv','representative_evidence.csv',
                 'vocal_cross_module_summary.csv','vocal_probability_gap_36_intervals.csv',
                 'latency_final_vs_sensitivity.csv','final_estimands_and_populations.csv','final_acceptance.json']+[f'stage{i}_metadata.json' for i in range(1,5)]:
        original=(source/name).read_bytes();canonical=original.replace(b'\r\n',b'\n')
        (dest/name).write_bytes(canonical)
        provenance.append(dict(path=name,source=(source/name).relative_to(ROOT).as_posix(),source_sha256=digest(source/name),transform='byte_copy' if original==canonical else 'line_endings_to_LF_only'))
    fields,rows=readcsv(source/'vocal_cross_module_diagnostic.csv');rows=[r for r in rows if r['scope']=='representative36']
    fields=[k for k in fields if k not in ['source_row_id','fold','scope','comparison_call_type']]
    writecsv(dest/'vocal_probability_conditions_36.csv',fields,rows)
    provenance.append(dict(path='vocal_probability_conditions_36.csv',source=(source/'vocal_cross_module_diagnostic.csv').relative_to(ROOT).as_posix(),source_sha256=digest(source/'vocal_cross_module_diagnostic.csv'),transform='representative36_only_no_raw_or_observed_rows',rows=len(rows)))
    notes=(source/'Q4_FINAL_INPUT_NOTES.md').read_text(encoding='utf-8')
    notes=notes.replace('全部结果见vocal_cross_module_diagnostic.csv及summary。','聚合结果见vocal_probability_conditions_36.csv及vocal_cross_module_summary.csv。观测/OOF逐行诊断仅在本地完整版中。')
    notes+='\n\n## 仓库交付范围\n\n本目录只含聚合结果和运行元数据；原始数据、逐条预测、配对映射、完整审计和NPZ均未上传。private_context_manifest.json列出复用所需私有历史文件的路径及哈希，需按docs/Q3_REPRODUCIBILITY.md从队内渠道恢复。历史报告中的results/及原附件链接只在恢复本地材料后可用。\n'
    (dest/'Q4_FINAL_INPUT_NOTES.md').write_text(notes,encoding='utf-8',newline='\n')
    manifest=[]
    for module,name,use in [('HVA','q4_combination_original_flags_36.csv','joint_original_flags_only'),('Latency','q4_latency_original_flags_36.csv','read_positive_time_availability_and_V_cdf_semantics'),('Count','q4_count_reused_36.csv','standalone_not_coherent_joint_with_HVA'),('paired_latency','latency_original_flags_paired.csv','matched_reference_not_36_scenarios'),('Duration','q4_duration_unavailable.csv','not_identified_no_numeric_input'),('evidence','representative_evidence.csv','not_observed_at_every_exact_scenario'),('cross_module','vocal_cross_module_summary.csv','constraints_unresolved_no_calibration'),('semantics','Q4_FINAL_INPUT_NOTES.md','mandatory_read')]:
        manifest.append(dict(module=module,path=name,sha256=digest(dest/name),use=use,version='final_original_flags_278',delivery_scope='shared_aggregate',interval_scope='fixed_model_confidence_not_future_prediction'))
    writecsv(dest/'q4_final_input_manifest.csv',list(manifest[0]),manifest)
    # Exact frozen dependencies of q3_final_revision.py, with no row contents.
    paths=['data/raw/playbacks/Data02_AfricanPenguins_playbacks_data.csv']
    stages={
      'q3_stage1_20261127T115630Z':['metadata.json','representative_support.csv'],
      'q3_stage2_20261127T115748Z':['oof_combinations.csv'],
      'q3_stage3_20261127T125020Z':['fit_diagnostics.json','count_predictions.csv','count_oof.csv'],
      'q3_stage4_20261127T125945Z':['latency_oof.csv','latency_predictions.csv','fit_diagnostics.json'],
      'q3_stage6_full_20261127T133654Z':['bootstrap_expID.npz','bootstrap_natural_track.npz','resampling_manifest.json','combination_predictions.csv','latency_intensity_predictions.csv','future_experiment_prediction_intervals.csv'],
    }
    for run,names in stages.items():paths.extend(f'results/q3/{run}/{name}' for name in names)
    r2='results/q3/round2/r2_20261127T155523Z'
    paths += [r2+'/R2_1/comparison_reference.csv',r2+'/R2_1/pair_mapping.csv',r2+'/R2_2/bootstrap_diagnostics.json',r2+'/R2_2/pattern_adjusted_contrasts.csv',r2+'/R2_2/pattern_bootstrap_expID.npz',r2+'/R2_2/pattern_bootstrap_natural_track.npz',r2+'/R2_3/count_paired_contrasts.csv',r2+'/R2_4/bootstrap_diagnostics.json']
    context={'scope':'private_frozen_inputs_not_published','files':[dict(path=name,bytes=(ROOT/name).stat().st_size,sha256=digest(ROOT/name)) for name in paths]}
    (dest/'private_context_manifest.json').write_text(json.dumps(context,ensure_ascii=False,indent=2),encoding='utf-8',newline='\n')
    meta=dict(source_run=source.relative_to(ROOT).as_posix(),input_sha256=acceptance['original_raw_sha256'],seed=20261127,
        code_identity='Git commit containing this release; source model hashes retained in stage metadata',
        release_kind='aggregate_research_delivery_not_standalone_raw_to_all_models_reproduction',
        raw_records_published=False,bootstrap_arrays_published=False,cross_module_constraints_pass=False,
        future_latency_prediction_intervals_updated=False,provenance=provenance)
    (dest/'release_provenance.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8',newline='\n')
    (dest/'release_manifest.json').write_text(json.dumps(dict(files=[dict(path=p.name,bytes=p.stat().st_size,sha256=digest(p)) for p in sorted(dest.iterdir()) if p.is_file()]),ensure_ascii=False,indent=2),encoding='utf-8',newline='\n')
    print('PACKAGED',len(provenance),'aggregate sources;',len(paths),'private dependency hashes;',sum(p.stat().st_size for p in dest.iterdir() if p.is_file()),'bytes')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,default=RELEASE);a=p.parse_args();build(a.source,a.output)
