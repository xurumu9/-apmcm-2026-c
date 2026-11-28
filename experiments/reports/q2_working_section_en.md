# Q2 working section: propagation fidelity and scenario ranges

**AI-generated working material for team review.** The team must independently assess the models, calculations, interpretations and competition rules. The intervals in this section are selected weight-scenario ranges, not statistical confidence intervals. They do not establish 95% coverage or bound the true communication distance.

## Data and fidelity

For each call type (flat, modulated, and two-voice), the supplied tables report spectrogram, amplitude-spectrum and amplitude-envelope correlations between recordings at 1 m and at 4, 8, 16, 32, 64, 128 and 256 m. At each call type, metric and distance, we calculate the mean over non-missing correlation values; the number of available correlations is 190–300 depending on the group. Values are not assumed to be independent recordings, and records are not paired across the three tables using their row positions.

Let S, A and E be the three mean correlations. At a fixed distance d and for nonnegative weights summing to one, define F(d)=wS S(d)+wA A(d)+wE E(d). The equal-weight case is used as an illustrative reference. Alternative settings are (0.6,0.2,0.2), (0.2,0.6,0.2) and (0.2,0.2,0.6), in the order S, A and E. These weights are assumptions rather than measured perceptual importance. Spectrogram correlations include multiple acoustic dimensions, so the composite components are not guaranteed to represent distinct information. The resulting fidelity is not a probability of penguin recognition or response.

## Candidate propagation curves

For each call type and weight setting, we apply equal-node-weight isotonic regression with a non-increasing constraint to the seven observed-distance composite means; adjacent fitted values are connected linearly. As a comparison, a constrained exponential curve F(d)=a+b exp(−d/τ) is fitted to the same seven means with a≥0, b≥0 and a+b≤1, searching 400 logarithmically spaced τ values from 4 to 2048 m. The chosen monotone assumption suppresses local increases and is not proof that actual propagation is strictly monotone. Predictions are restricted to 4–256 m.

## Threshold ranges

The thresholds 0.3, 0.5 and 0.7 are illustrative low, intermediate and stringent recognition scenarios; none is a validated penguin hearing threshold. For a non-increasing candidate curve, we report the first crossing from at least T to below T. If T is already unmet at 4 m, or is still met at 256 m, we report the corresponding boundary state rather than extrapolating.

| Call type | Threshold | Equal-weight estimate (m) | Range across four weight scenarios (m) |
|---|---:|---:|---:|
| flat | 0.3 | 169.14 | 127.94–185.69 |
| flat | 0.5 | 89.90 | 62.87–101.04 |
| flat | 0.7 | 36.64 | 21.92–51.66 |
| mod | 0.3 | 235.00 | 223.38–241.56 |
| mod | 0.5 | 150.47 | 120.87–166.79 |
| mod | 0.7 | 81.91 | 26.99–95.89 |
| tv | 0.3 | 247.84 | Minimum 227.25; at least one scenario remains above threshold at 256, so the maximum is unknown |
| tv | 0.5 | 180.10 | 154.29–194.47 |
| tv | 0.7 | 83.76 | 10.00–128.33 |

At T=0.5 with equal weights, the estimated order is tv > mod > flat. This is conditional on the stated model, weights and threshold; it is not established as a universal ranking. The tv result at T=0.3 is close to the edge of observation, and the threshold 0.7 results for mod and tv are highly sensitive to the chosen weights.

## Model comparison and checks

At T=0.7 with equal weights, the exponential candidate gives 33.44 m for flat, 53.90 m for mod and 45.86 m for tv, compared with 36.64, 81.91 and 83.76 m under isotonic regression. A leave-one-distance-out check uses the five interior levels 8–128 m; isotonic/exponential mean absolute errors are 0.0447/0.0390 for flat, 0.0479/0.0498 for mod, and 0.0551/0.0750 for tv. These are errors in fidelity units, not metres. Five distance levels are too few to establish generalization or choose a universally best model; there is no independent marine-condition test.

The four-scenario ranges only describe sensitivity to the selected weights. They are not statistical confidence intervals and cannot be interpreted as 95% coverage. The propagation study used three original call examples per type, repeated recordings, and pairwise correlations sharing recordings [1]. The available CSV files lack sufficient confirmed labels to reconstruct their full dependence structure, and three original examples per type are too few for a stable general inference. We therefore leave statistical interval limits unavailable rather than treating all correlation rows as independent. The source propagation experiment was conducted over an inland reservoir under calm conditions [1], so application to noisy or rough ocean conditions is limited.

The P1 exploratory handoff can provide background on differences among call types; its acoustic classification outputs do not directly determine the three correlation weights or a penguin perceptual threshold [2]. Q3 group behavioral responses are also not identical to hearing a call; the integration with Q4 remains pending the behavioral model and a team-defined index.

## Source references (team must reconcile numbering and verify)

[1] Thiebault A, Huetz C, Aubin T, et al. Contact and recruit – the importance of acoustic communication in the foraging strategy of a flightless seabird. Open Research Europe, 2026. https://doi.org/10.12688/openreseurope.24618.1

[2] P1 team, exploratory acoustic handoff, commit f75abf4: https://github.com/xurumu9/-apmcm-2026-c/blob/f75abf4/experiments/reports/q1_handoff_q2_q3.md
