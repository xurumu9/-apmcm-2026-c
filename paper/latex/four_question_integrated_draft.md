# Acoustic Communication and Playback Responses of African Penguins at Sea

**Integrated working draft for team review.** This document combines Q1 and Q4 from commit `057d203`, Q2 from `6306e8e`, and Q3 from `9a7e06f`. It is a scientific-content draft, not the contest's final formatted paper. The team must review the models, evidence, AI-use disclosure, references, figures and complete submission requirements. The original Q2 and Q3 models and files have not been changed.

## 1. Data and modeling framework

We study flat, modulated (mod) and two-voice (tv) sea-surface calls using three complementary datasets: Data01 contains acoustic measurements; Data03–11 contain propagation correlations; and Data02 contains marine playback observations. Q1 describes and classifies calls, Q2 models acoustic fidelity across distance, Q3 estimates recorded group behavior after playback, and Q4 combines the aggregate results in an explicitly hypothetical effectiveness scenario. Call type provides a common descriptive interface. The datasets do not have confirmed record-level linkage, and rows from different experiments are not paired.

Our results describe the supplied experiments and specified assumptions. A recorded response is not equivalent to perception; failure to observe a response does not establish failure to hear a stimulus. We distinguish an assumed scenario index from independently calibrated response probabilities and from observed responder counts.

## 2. Acoustic characteristics and classification

Data01 contains 108 calls: 44 flat, 40 mod and 24 tv. Duration, F01, Fpeak and spectral quartiles Q25, Q50 and Q75 were recorded for all three types. F02 was recorded for all 24 tv calls and not recorded for flat or mod. Pulse rate was recorded for 34 mod and 20 tv calls and was absent from the flat records. Missing measurements were not replaced with zero. The distributions and valid sample sizes are illustrated in [Figure 1](../../figures/q1_acoustic_features.png); the full medians and interquartile ranges appear in the [Q1 feature table](../../experiments/reports/q1_feature_table.md).

We compared the six shared features using a Kruskal–Wallis overall test with Holm correction across features and separate two-sided pairwise rank-sum permutation tests with Holm correction across 18 comparisons. Fpeak differed among call types (H=12.276, adjusted p=0.01296). Its medians were 916, 831 and 829.5 Hz for flat, mod and tv. The flat–mod comparison yielded adjusted p=0.0171 and rank-biserial effect size 0.409, indicating higher Fpeak values for flat calls in this sample. The corrected overall p-value for F01 was 0.0517. A nonsignificant result does not establish equal distributions. Individual identities and independence are not confirmed; the tests are exploratory.

We investigated a conditional two-stage classifier: records with F02 present are assigned tv, and the remaining records are assigned flat or mod by a CART using the six shared features and a pulse-rate-recording indicator. The tree uses Gini impurity, depth at most three and a minimum leaf size of three. With leave-one-date-out fitting for the second stage and the fixed first-stage rule, 103/108 labels agreed (95.37%, macro-F1 0.960). The confusion matrix, in flat/mod/tv order and with true classes as rows, is `[[42,2,0],[3,37,0],[0,0,24]]`. Three of six mod records without pulse-rate measurements were correctly classified. The rule and model were selected after examining these data, and recording status may reflect the original measurement or classification process. This is not an independent estimate of performance on new recordings.

Fpeak supplies a shared frequency descriptor; Q25–Q75 summarize the spectral distribution; F02 and pulse rate describe structural properties when recorded. These Data01 measurements are not directly fitted as continuous predictors in Q2 or Q3. Q2 and Q3 instead share the call-type label, and their outcomes cannot establish that a particular acoustic feature caused a propagation or behavioral difference.

## 3. Signal propagation and fidelity

For each call type and distance, Q2 averages the available spectrogram, amplitude-spectrum and amplitude-envelope correlations relative to a 1 m reference. With weights w_S, w_A and w_E that are nonnegative and sum to one, define `F(d)=w_S S(d)+w_A A(d)+w_E E(d)`. The baseline is equal weights. Non-increasing isotonic regression is applied to the seven distance-specific means at 4, 8, 16, 32, 64, 128 and 256 m, with linear interpolation; a constrained exponential curve is a comparison. These assumptions do not prove that the real signal decays monotonically or that all three indicators measure distinct information.

The following table gives first crossings of illustrative thresholds, in meters, under equal weights. Thresholds 0.3, 0.5 and 0.7 represent hypothetical potential, intermediate and more stringent recognition conditions, not experimentally validated hearing thresholds.

| Call type | 0.3 | 0.5 | 0.7 |
|---|---:|---:|---:|
| flat | 169.14 | 89.90 | 36.64 |
| mod | 235.00 | 150.47 | 81.91 |
| tv | 247.84 | 180.10 | 83.76 |

At threshold 0.5 the conditional order is tv > mod > flat, but the conclusion depends on weights, threshold and model. The four selected weight scenarios provide sensitivity ranges, not 95% confidence intervals: at 0.5 they are 62.87–101.04 m, 120.87–166.79 m and 154.29–194.47 m, respectively. The propagation data include shared recordings, only three original call examples per type, and an inland-water experiment; independent sample size and generalization to sea conditions remain limited. Predictions are restricted to the observed 4–256 m range. Details and additional boundary cases are in the [Q2 working section](https://github.com/xurumu9/-apmcm-2026-c/blob/6306e8e/experiments/reports/q2_working_section_en.md).

## 4. Marine playback responses

Q3 retains 278 observations from 139 paired experiments and models the eight joint combinations of the original head-up (H), vocal (V) and approach (A) markers. In these records, V is exactly `I(N_after > N_before)`, not a general indicator of any vocalization. The state 000 means no original marker was positive; it does not imply no calling or no perception.

For supported type-specific matched reference populations, the estimated difference in probability of at least one original marker between a natural call and its corresponding wave control was 40.25 percentage points (95% pointwise interval 28.84–52.34) for flat, 39.82 (27.08–53.29) for mod and 47.02 (36.26–57.71) for tv. The populations comprise 30, 20 and 39 supported pairs, respectively, and differ across types; the estimates do not establish a direct ranking. Adjusted differences in expected actual call counts were 1.178 (0.764–1.652), 1.706 (0.830–2.706) and 1.481 (1.060–2.000) calls per playback, respectively.

The response-combination model supplies the window probabilities for the three markers. Recorded conditional response times are modeled separately by type. The vocal cumulative quantity combines a final positive vocal-increase flag with a recorded vocal time by t; it is not the time when cumulative calls first exceed baseline. True behavioral duration remains unidentified because the interpretation of the 60-second encoding is unresolved. Control approach has no positive time observations, so its conditional time results depend on borrowed model information.

The following conditional medians, in seconds, are the Q3 after-context predictions for N=8 and baseline vocal count 0. They are the same at 50, 100 and 150 m because this conditional-time model uses call type only; this is a model constraint, not evidence that distance has no effect on latency. Observation support varies by behavior and distance: several cells are extrapolated or unverified, and the control approach estimate has no positive control approach times. Full condition-specific probabilities, uncertainty and support labels must accompany the final table.

| Playback | Head-up | Vocal-increase label | Approach |
|---|---:|---:|---:|
| wave control | 1.56 | 3.48 | 8.09 |
| flat | 1.82 | 3.09 | 8.13 |
| mod | 1.76 | 2.71 | 7.84 |
| tv | 2.19 | 3.54 | 8.31 |

The probability of the vocal-increase flag and the independently modeled probability of any post-playback call should obey event constraints, but the separately fitted modules do not always do so. Ten of the 36 zero-baseline scenarios have a vocal-increase probability above the count model's probability of any call. The HVA model and count model may be presented individually; their outputs must not be combined as though they were an internally consistent joint distribution. See the [Q3 final synthesis](https://github.com/xurumu9/-apmcm-2026-c/blob/9a7e06f/experiments/reports/Q3_FINAL_RESEARCH_SYNTHESIS.md), [representative latency table](https://github.com/xurumu9/-apmcm-2026-c/blob/9a7e06f/experiments/reports/q3_release/q4_latency_original_flags_36.csv) and [Q4 input notes](https://github.com/xurumu9/-apmcm-2026-c/blob/9a7e06f/experiments/reports/q3_release/Q4_FINAL_INPUT_NOTES.md) for estimands, uncertainty and support labels.

## 5. Effectiveness and conservation scenarios

Let F_c(d) be the Q2 fidelity curve, r a hypothetical proportional reduction, and F'=(1-r)F_c(d). For Q3 marker probabilities p_H, p_V and p_A, define a weighted behavior score `B=w_H p_H+w_V p_V+w_A p_A`, where weights are nonnegative and sum to one. The reference gives each marker equal weight; additional scenarios give one marker weight 0.6 and each remaining marker 0.2. Equal weights express equal analytical emphasis, not demonstrated equality of ecological value.

The baseline smooth fidelity factor is `g=min(1,max(0,(F'-(T-Δ/2))/Δ))`, with T=0.5 and total transition width Δ=0.1. The scenario score is `E=gB`. We compare widths 0.05 and 0.20 and a hard threshold. This is a constructed score, not a calibrated recognition or behavioral probability. Since Q3 already includes distance, applying g may duplicate some distance-related effects; the separate experiments do not establish a causal link between fidelity and behavioral response.

For the after context, N=8, zero calls before playback and r=0, smooth scores at 50, 100 and 150 m are 0.358, 0.039 and 0 for flat; 0.363, 0.308 and 0.136 for mod; and 0.380, 0.327 and 0.295 for tv. A zero score follows from the assumed factor and does not mean no response. The 150 m flat and mod scenarios are extrapolated under Q3's support labeling; tv is at a boundary.

As the alternative to a radius, we consider `N_s=Nπg p_any`, where p_any is the Q3 probability of at least one original marker and π is an assumed proportion of participants conditional on that group event. Neither π nor the mapping g p_any is identified by observed individual responses under noise. Under π=0.5 at 50 m in this setting, N_s is 2.42, 2.48 and 2.72 individuals per playback for flat, mod and tv; π=0.25 and 0.75 are sensitivity scenarios. These are hypothetical expected counts, not measured individual responses. Multiplication by g can alter the Q3 prediction even when r=0; it should not be presented as an empirically calibrated correction.

We compare fidelity reductions of 5%–20% and threshold values 0.5–0.7 as scenarios rather than measured noise effects. In a grid of 45 context/distance/reduction combinations, the set of highest-scoring types changes across three transition widths in eight cases; this is a grid-dependent sensitivity count, not a probability or statistical test. No joint Q4 confidence interval is claimed. [Figure 2](../../figures/q4_sensitivity.png) displays selected scenarios, and [Q4 details](../../experiments/reports/q4_input_handoff.md) record the calculations and limitations.

Future propagation studies should use more independently sourced calls and measure actual noise and sea states. Playback studies should track individual participants, call identities, noise, sound level, response timing and paired-trial intervals. In identified foraging areas, managers may consider noise monitoring and trialing vessel avoidance, speed limits or quieter operations, with before–after and comparison-area evaluation. The assumed thresholds do not define a legal protection boundary; increased observed group response does not by itself demonstrate improved foraging or population recovery.

## 6. Integration limits and sources

The main cross-question connection is by call type, not individual recording. Q1 classification is conditional on supplied structural-record indicators; Q2 threshold distances are conditional acoustic-fidelity crossings; Q3 is a group-level playback model; and Q4 is an assumption-dependent scenario index. They answer related but distinct questions. The absence of measured noise-response calibration is a limitation of the available data and does not prevent explicitly labeled scenario analysis.

Primary data source: [Zenodo dataset record](https://zenodo.org/records/21376649). Research background: Thiebault A, Huetz C, Aubin T, et al., *Contact and recruit – the importance of acoustic communication in the foraging strategy of a flightless seabird*, Open Research Europe, 2026, [doi:10.12688/openreseurope.24618.1](https://doi.org/10.12688/openreseurope.24618.1). The team must verify final bibliographic details, source numbering, the contest AI-use requirements, and the manuscript against actual team decisions. This draft does not yet include the final abstract, full Q3 representative tables, formatted references or a compiled PDF.
