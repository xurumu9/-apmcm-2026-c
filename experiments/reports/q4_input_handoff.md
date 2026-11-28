# 第四问：现有输入与建模交接

## 第四问候选模型与初步计算（2026-11-28）

按用户选择，以三类行为等权为基准，并将保真度从硬门槛改为平滑过渡，不另设效能分数门槛。模型供队伍审阅：`src/python/q4_scenarios.py` 计算硬门槛基线及输入元数据，`src/python/q4_gate_sensitivity.py` 生成平滑主方案和宽度对照；原始 Q2/Q3 模型未重新拟合。

### 平滑主方案的代表结果

以 T=0.5、过渡总宽度 Δ=0.1 为基准，即在 0.45 至 0.55 内线性过渡；范围之外分别取 0 或 1。三种行为等权，after 情境、群体规模 8、播放前发声次数 0、无额外退化时：

| 类型 | 50 m | 100 m | 150 m |
|---|---:|---:|---:|
| flat | 0.358 | 0.039 | 0 |
| mod | 0.363 | 0.308 | 0.136 |
| tv | 0.380 | 0.327 | 0.295 |

这些是设定下的平滑效能得分，不是响应概率；flat、mod 150 m 的 Q3 条件标为 extrapolation，其余行的支持标签见后文。若假设已有任一原标记的群体中 50% 个体参与，则 50 m 的情景期望 flat、mod、tv 分别为 2.42、2.48、2.72 人；该比例及平滑系数均非实测。0.1 为假设过渡宽度，另以 0.05 和 0.2 比较；不得因曲线更平滑而声称已验证更符合实际。

### 门槛平滑对照：探索性敏感性

原方案保留硬门槛 G=1[F'≥T]，其中 F'=(1-r)F。为了检验门槛附近的跳变，引入仅供对照的线性过渡：`G_s = min(1, max(0, (F' - (T - Δ/2))/Δ))`，相应得分为 `E_s=G_s(w_H p_H+w_V p_V+w_A p_A)`。在 T=0.5、过渡宽度 Δ=0.1 的例子中，F'≤0.45 时系数为 0，F'≥0.55 时为 1，中间线性变化，F'=0.5 时为 0.5。Δ 另取 0.05、0.2 进行敏感性分析；该宽度是人为假设，不由实测识别数据估计。

after 情境、150 m、群体规模 8、三行为等权、T=0.5 时，硬门槛与 Δ=0.1 的对照如下。Q3 的 mod 在这一条件为 extrapolation，tv 为 boundary；不能将这些情景变化解释为实测噪声效应。

| 类型 | 假设相关性下降 | 调整后保真度 | 硬门槛得分 | 平滑得分 |
|---|---:|---:|---:|---:|
| mod | 0% | 0.501 | 0.267 | 0.136 |
| mod | 5% | 0.476 | 0 | 0.070 |
| mod | 10% | 0.451 | 0 | 0.003 |
| tv | 10% | 0.530 | 0.295 | 0.236 |
| tv | 15% | 0.501 | 0.295 | 0.149 |
| tv | 20% | 0.471 | 0 | 0.062 |

平滑方案在示例门槛附近给出渐变评分，避免硬规则中小幅输入变化造成评分跳变；但它允许略低于 T 的情景有非零分，因此不再具有“达标/未达标”的严格含义。两个系数都不是经过企鹅感知实验标定的识别概率，平滑也不能自动解决 Q2/Q3 之间潜在的距离重复计入。依用户选择，**平滑过渡作为当前主方案，硬门槛作为敏感性对照**；不因曲线更平滑就称其已验证更接近现实。

先运行 `python src/python/q4_scenarios.py`，再运行 `python src/python/q4_gate_sensitivity.py`，生成被 Git 忽略的 `results/q4/gate_sensitivity.csv`，共 1,215 行（27 个条件×3 个阈值×5 个退化比例×3 个过渡宽度）。人数对照将原先假设的 50% 条件参与比例情景乘上同一平滑系数，同样不是噪声下实测或标定的响应人数；不提供统计置信区间。

### 过渡宽度是否影响类型比较

固定平滑中心 T=0.5、三行为等权，比较总宽度 Δ=0.05、0.10、0.20；即过渡区间分别为 [0.475,0.525]、[0.45,0.55]、[0.40,0.60]。以下为 after 情境、8 只企鹅、播放前发声数 0、假设相关性下降 20% 时的效能评分：

| 距离 | 总宽度 Δ | flat | mod | tv | 该情景的最高评分 |
|---:|---:|---:|---:|---:|---|
| 50 m | 0.05 | 0.317 | 0.363 | 0.380 | tv |
| 50 m | 0.10 | 0.248 | 0.363 | 0.380 | tv |
| 50 m | 0.20 | 0.214 | 0.363 | 0.335 | mod |
| 100 m | 0.05 | 0 | 0.240 | 0.327 | tv |
| 100 m | 0.10 | 0 | 0.197 | 0.315 | tv |
| 100 m | 0.20 | 0 | 0.175 | 0.239 | tv |
| 150 m | 0.05 | 0 | 0 | 0 | 并列 |
| 150 m | 0.10 | 0 | 0 | 0.062 | tv |
| 150 m | 0.20 | 0 | 0.001 | 0.105 | tv |

在 3 个情境×3 个距离×5 个相关性下降比例的 45 个设定中，比较三种宽度下最高评分的类型集合：37 个设定相同、8 个设定发生变化（包含全部评分为零的并列变为单一最高）。这是对选定网格的确定性计数，不是概率或统计显著性检验；改变权重、阈值或网格可能得到不同结果。after、50 m、下降 20% 的最高评分由 tv 变为 mod，是结论依赖宽度的具体例子；该处的条件支持应按 Q3 原标签解释。150 m 的 mod 属 Q3 extrapolation，flat 为 extrapolation，tv 为 boundary。宽度的影响和 Q3/Q2 输入不确定性尚未整合成置信区间。总体上应报告评分对宽度敏感的条件，不能将某类叫声宣布为所有环境下的最优类型。

### 假设下的响应概率情景

为回应题目要求比较噪声下响应概率，可另设情景量 `P_s=G_s P(any original H/V/A marker)`。它需要额外假设：Q3 的条件群体标记概率可与平滑因子如此结合；这一关系没有通过噪声回放数据验证，并且可能与 Q3 中已有的距离影响重复。它只是模型情景概率，不是噪声实验观测或已校准预测，也不是 Q3 原本给出的概率；后者仍单独保留。假设至少一个标记出现时的个体参与比例为 π，则情景人数 `N_s=8πP_s`。

下表为 after、100 m、N=8、基线发声数 0、平滑宽度 0.1 的示例；两列概率分别为 r=0 和 r=20% 假设下的 `P_s`。这些是条件于本模型的估计，两个 r 值之间不能单独解释为噪声的实测因果效应。

| 类型 | Q3 原群体标记概率 | 情景概率，r=0 | 情景概率，r=20% | 假设 π=0.5 时的情景人数，r=0 → 20% |
|---|---:|---:|---:|---:|
| flat | 0.564 | 0.071 | 0 | 0.28 → 0 |
| mod | 0.554 | 0.554 | 0.354 | 2.22 → 1.42 |
| tv | 0.660 | 0.660 | 0.637 | 2.64 → 2.55 |

因为 Q3 是已经包含距离的原观察条件模型，即使 r=0，乘上 G_s 也会改变其原概率；例如 flat 从 0.564 改为 0.071。这是情景假设导致的差异，不是新观测、外部校准或基准下真实概率的修正。若这个假设不能被队伍接受，则应只报告 Q3 原概率和 Q4 效能评分，并明确当前无法识别噪声下实际响应概率变化。

## 第四问英文论文草稿

### Communication effectiveness and scenario analysis

We combine the Q2 acoustic-fidelity curve with the Q3 behavioral model through an illustrative score, while retaining their different experimental contexts. For call type c and distance d, let F_c(d) be the Q2 equal-weight fidelity estimate and let p_H, p_V and p_A be the Q3 probabilities of the original head-up, vocal-increase and approach markers, respectively. We set B=w_H p_H+w_V p_V+w_A p_A, with nonnegative weights summing to one. Equal weights form the baseline, representing equal emphasis on the three measured signals rather than established equality of their ecological importance; alternative weights emphasize one behavior at a time.

For a hypothetical proportional fidelity reduction r, let F'=(1-r)F_c(d). We define a smooth fidelity factor g=min{1,max[0,(F'-(T-Δ/2))/Δ]}, and the effectiveness score E=gB. The baseline uses T=0.5 and a total transition width Δ=0.1. The factor provides a gradual change around an illustrative threshold; it is not a measured recognition probability. We compare transition widths of 0.05 and 0.2 and a hard threshold as sensitivity scenarios. Because the Q3 behavioral model already includes distance, applying an additional fidelity factor may count some distance-related effects twice. Consequently, E is a scenario index, not a calibrated probability of a penguin response.

For the after context at a group size of eight, zero prior vocalizations and no additional reduction, the smooth scores at 50, 100 and 150 m are 0.358, 0.039 and 0 for flat calls; 0.363, 0.308 and 0.136 for modulated calls; and 0.380, 0.327 and 0.295 for two-voice calls. The Q3 predictions at 150 m for flat and modulated calls are labeled extrapolation and those for two-voice calls boundary; they should not be interpreted as direct observations. Scores depend on the selected threshold, transition width, behavioral weights and the original models.

We illustrate the alternative target of expected respondent numbers using N_s=8πg p_any, where p_any is Q3's probability of at least one original H/V/A marker and π is an assumed participating fraction conditional on that group marker. The data do not identify π. For π=0.5 in the after context at 50 m, the illustrative expectations are 2.42, 2.48 and 2.72 individuals per playback for flat, modulated and two-voice calls; π=0.25 and 0.75 are sensitivity settings. The quantity g p_any can also serve as a hypothetical scenario response probability, but its relationship to noisy-playback responses is unvalidated and it may differ from the original Q3 prediction even when r=0. It must not be reported as a measured or calibrated probability. A score threshold and hence a Q4 effective radius were not specified; the modeled respondent count is the selected alternative requested by the problem.

We compare hypothetical fidelity reductions of 5%–20%, threshold values of 0.5–0.7, behavioral weights and transition widths. For example, in the after context at 100 m, the model's hypothetical group-marker probability proxy changes from 0.554 to 0.354 for modulated calls and from 0.660 to 0.637 for two-voice calls when r increases from zero to 20%, conditional on the smooth-factor assumption. These are not measured noise effects. Among 45 selected combinations of context, representative distance and reduction, the set of types with the highest score changes across the three widths in eight combinations. This is a grid-specific sensitivity check, not evidence of a universal ranking or statistical significance. No joint confidence interval is claimed: reliable Q2 sampling intervals are unavailable and the public Q3 aggregate does not contain the joint bootstrap replicates needed for this calculation.

### Experiment design and conservation implications

Future studies should repeat propagation measurements at sea across noise and sea conditions, increase independently sourced calls, and retain recording and individual identifiers. Playback experiments should record individual participation, baseline calls, sound levels, context, noise, behavioral timing and paired-trial intervals. These measurements would help estimate the participation fraction and test the relationship between fidelity and behavior. In identified foraging areas, managers could consider monitoring underwater noise and trialing vessel avoidance, speed restrictions or quieter operations at relevant times, followed by before–after and comparison-area evaluation. The present scenario thresholds and ranges are not prescribed protection boundaries, and observed group responses do not establish improved foraging or population recovery.

**整合提示：**配图见 [Q4 敏感性图](../../figures/q4_sensitivity.png)，数值来自 `results/q4/scenario_summary.csv` 与 `results/q4/gate_sensitivity.csv`；来源为 Q2 `6306e8e` 和 Q3 `9a7e06f` 的聚合报告。论文引用、编号、英文修订和团队审阅尚未完成。

设 Q2 的等权保真度为 F_c(d)，噪声或海况情景下假设相关性下降比例为 r，识别情景阈值为 T；Q3 的三个原标记边际概率分别为 p_H、p_V、p_A，行为权重 w_H+w_V+w_A=1，均非负。硬门槛对照定义 G=1[(1-r)F_c(d)≥T]，其评分为 E=G(w_H p_H+w_V p_V+w_A p_A)；当前主方案以本节上方定义的平滑系数 G_s 替换 G。基准权重为 (1/3,1/3,1/3)；敏感性分别为 (0.6,0.2,0.2)、(0.2,0.6,0.2)、(0.2,0.2,0.6)。等权体现暂不偏好某一类行为，并不表示这些行为的生态价值已被证实相等；偏重情景分别表达关注警觉、发声增加或接近。

E 是人为构造的**情景评分**，不是个体或群体响应概率。因为 Q3 行为概率已包含回放距离效应，本模型不把保真度当成独立概率再乘入；G 仅作为额外的情景达标条件。G=0 时评分按定义置零，并非观测到无响应或无感知；门槛引入的人为跳变不能解释为真实行为突然消失。Q2 的传播实验与 Q3 的海上回放并非相同实验，跨实验组合不能保证消除重复距离影响。噪声下仍沿用原 Q3 行为预测，没有对噪声—行为关系进行实测标定。

### 硬门槛对照：after 情境、8 只企鹅、播放前发声次数为 0

下表分别报告保真度、原行为等权得分与条件得分；阈值 T=0.5、r=0。评分 0 表示门槛未达标，并非实测零响应。

| 类型 | 距离 m | 保真度 F | 原行为得分 | 条件得分 E | Q3 联合支持 |
|---|---:|---:|---:|---:|---|
| flat | 50 | 0.649 | 0.358 | 0.358 | boundary |
| flat | 100 | 0.463 | 0.310 | 0 | boundary |
| flat | 150 | 0.327 | 0.275 | 0 | extrapolation |
| mod | 50 | 0.757 | 0.363 | 0.363 | interpolation |
| mod | 100 | 0.642 | 0.308 | 0.308 | interpolation |
| mod | 150 | 0.501 | 0.267 | 0.267 | extrapolation |
| tv | 50 | 0.721 | 0.380 | 0.380 | boundary |
| tv | 100 | 0.683 | 0.327 | 0.327 | boundary |
| tv | 150 | 0.589 | 0.295 | 0.295 | boundary |

这些仅为一个情境的模型预测；表中 boundary 和 extrapolation 沿用 Q3 原标签，尤其 mod 150 m 属外推。50、100、150 m 为代表条件，不应把最远达标网格点当作连续精确半径。

### 权重与硬门槛噪声敏感性

同一 after、50 m、基准阈值和无额外退化下，四种行为权重的得分如下；数值为等权、偏重抬头、偏重发声、偏重靠近的顺序：flat **0.358、0.405、0.414、0.254**；mod **0.363、0.410、0.382、0.296**；tv **0.380、0.394、0.438、0.307**。这些差异展示权重假设的影响，不代表偏重某行为更真实。

阈值从 0.5 升至 0.6 后，该情境下 mod、tv 在 150 m 不达标；升至 0.7 后，flat 在三个代表距离均不达标，mod 与 tv 仅 50 m 达标。当阈值为 0.5、相关性假设下降 20% 时，mod 与 tv 的 150 m 得分从各自基准值变为 0；flat 的达标状态不变。这里的零值只反映模型的门槛规则，不能称噪声导致实测响应概率归零。完整结果覆盖 5%、10%、15%、20% 的退化及其他情境。

### 假设响应人数

设 π 为“在至少出现一种原行为标记的群体中，参与响应的个体比例”，情景预期人数定义为 8×P(any H/V/A)×π×G。π 不是 Data02 已测得的个体响应比例，取 0.25、0.50、0.75 作敏感性示例；相关性门槛为零的情景人数同样是模型约定，不是对实际无人的观测。

after、50 m、T=0.5、r=0 且 π=0.5 时，flat、mod、tv 分别为 **2.42、2.48、2.72 人次/次播放**的条件情景期望；这不是实际计数或已验证的个体概率。比例改为 0.25 或 0.75 时，数值分别为上述结果的 0.5 倍或 1.5 倍。群体行为标记可能由不同个体产生，参与比例假设需要未来个体层面数据验证。效能分数门槛未被设定，故这里选择题目允许的“响应人数情景”而不声称得到综合效能半径。

### 复现与不确定性

代码从 Git 中读取 Q2 `6306e8e` 的汇总均值与 Q3 `9a7e06f` 的 36 条件联合概率；需先确保两次提交在本地 Git 对象中。使用等节点权重 PAVA 和线性插值重建 Q2 候选曲线，检查每个条件八个 HVA 概率非负且和为一；输出 4,860 行（27 条件×4 行为权重×3 阈值×5 退化情景×3 响应比例）。不输出置信区间：Q2 缺少可靠统计区间，Q3 聚合状态区间不能直接相加；Q3 的 Bootstrap 联合重复材料也未包含在公开仓库。输出的全部数量均为固定模型下的情景点值。

2026-11-28，供队伍独立建模与论文整合。Q2 使用 `6306e8e`，Q3 使用 `9a7e06f`；本次未更改或重新拟合两问。比赛题目要求团队构建效能指标、解释权重，估计典型群体的效能半径或预期响应人数，分析响应比例及噪声情景，并提出有条件的保护建议。题目没有指定效能公式或半径判据。

## Q2 可直接引用的传播情景

下表为 Q2 单调拟合、三指标等权时的阈值交点（米），距离观测范围 4–256 m。0.5、0.6、0.7 是假设阈值；相关性下降 20% 也是情景假设，并非实测噪声效应。

| 类型 | 基准阈值 0.5 | 阈值 0.6 | 阈值 0.7 | 相关性下降 20%、阈值 0.5 |
|---|---:|---:|---:|---:|
| flat | 89.90 | 62.95 | 36.64 | 56.37 |
| mod | 150.47 | 113.30 | 81.91 | 105.45 |
| tv | 180.10 | 146.24 | 83.76 | 137.77 |

这些数是 Q2 的**保真度阈值交点**，并非已建立的 Q4 综合效能半径；不能直接称为实测通信或识别半径。权重情景范围不是置信区间，实验每类只有三个原始叫声样例，独立性和海况外推均受限。完整 5%–20% 情景及边界状态见 [Q2 情景表](https://github.com/xurumu9/-apmcm-2026-c/blob/6306e8e/experiments/reports/q2_candidate_noise_sensitivity.csv)。

## Q3 代表条件：原行为标记概率

表中为 `1−P(000)`，即至少一项原始 H/V/A 标记为 1 的模型概率；直接由 [Q3 联合状态表](https://github.com/xurumu9/-apmcm-2026-c/blob/9a7e06f/experiments/reports/q3_release/q4_combination_original_flags_36.csv)中的 `000` 行计算，选 `expID` 结果。条件为 context=after、Npenguins=8、播放前发声数=0；每格括号保留 Q3 原联合支持标签。只展示一个情境，不代表其他情境或全情境平均。

| 类型 | 50 m | 100 m | 150 m |
|---|---:|---:|---:|
| flat | 0.6058（boundary） | 0.5636（boundary） | 0.5523（extrapolation） |
| mod | 0.6200（interpolation） | 0.5540（interpolation） | 0.5195（extrapolation） |
| tv | 0.6803（boundary） | 0.6603（boundary） | 0.6766（boundary） |

这些是模型预测的群体级**任一记录行为标记**概率，不是个体响应概率或人数。000 仅表示三个原标记均为零，V 表示播放后发声次数大于播放前；不能解释为无发声、无感知或无行为。Q3 的 36 情景含不同类型、情境、距离及对照，全部应保留其各自支持标签。该表不展示不确定性；完整状态各自的区间不能简单相加得出任一标记概率或综合指数的区间。

## 敏感性图与保护建议

[第四问敏感性图](../../figures/q4_sensitivity.png)展示平滑主方案（T=0.5、Δ=0.1）、after 情境、群体规模 8：A 在 50 m 比较行为权重，B 在 50 m 比较假设参与比例，C 在 150 m 比较假设保真度下降。Flat 在 150 m 的平滑系数为 0，Mod 在 150 m 的 Q3 行为结果为 extrapolation，TV 为 boundary。图没有置信区间，三类叫声的条件预测不等于已证明的整体排序。先运行 `q4_scenarios.py`，再运行 `q4_sensitivity_figure.py` 重现。

建议英文图注：*Sensitivity of illustrative communication-effectiveness scenarios for the after context and a group size of eight. The smooth fidelity factor uses a midpoint of 0.5 and a transition width of 0.1. (A) Alternative behavior weights at 50 m. (B) Assumed proportion of individuals responding conditional on a group marker at 50 m. (C) Assumed proportional reduction in fidelity at 150 m, using equal behavior weights. A zero score reflects the assumed fidelity factor, not observed absence of responses. The mod prediction at 150 m is extrapolated, and the corresponding tv prediction is at the boundary of joint support.*

实验和管理建议需由队伍结合保护区资料及实际管理权限确认：

1. **改进传播实验：**在企鹅实际觅食海域、不同海况和背景噪声水平下，测量不同距离的信号及噪声；增加独立叫声和独立个体样本，保留录音来源与重复测量标识。这样才能检验内陆水域估计在海上的适用性。
2. **改进回放实验：**在控制播放声级、距离与声源的同时，记录企鹅个体身份、实际参与数量、行为启动时间和背景噪声；平衡叫声类型与对照的顺序及情境，并明确配对间隔。这样可以直接估计目前只能假设的个体参与比例，也可检验噪声与行为之间的联系。
3. **保护觅食海域：**在已识别的重要觅食时段和区域，结合现场噪声监测与企鹅活动观测，试行船舶避让、限速或低噪声航行，并开展实施前后对照评估。措施的区域、时段与力度应由现场数据、航运条件和管理部门共同确定；本模型的假设阈值及距离不直接构成法定保护边界。
4. **持续监测和调整：**将船舶活动、噪声水平、觅食群体和行为响应一起记录，比较措施实施前后及对照区域的变化，并在不同海况下复查；群体响应增加不一定等于觅食成功率或种群恢复。

## 第四问团队建模时需解决的接口

- **距离与保真度：**Q3 的行为预测已包含距离效应；若再使用 Q2 的随距离保真度相乘，可能重复计入同一传播影响，且现有数据未标定保真度到行为概率的条件关系。需要明确效能指数的解释和假设，不能把未经校准的乘积直接称为响应概率。
- **生态权重和阈值：**需定义不同行为或情境的权重、尺度、阈值及其生态解释，并对设定做敏感性分析；Q2 阈值交点不能直接当作综合效能半径。
- **群体与个体：**Q3 群体事件概率不识别响应的个体数。若估计人数，须明确群体响应下的个体参与比例等附加假设及其敏感性，不能直接把 Npenguins 乘以群体响应概率解释为实测人数。
- **噪声与海况：**现有 Q2 仅有相关性或阈值的假设情景，未建立声噪到行为概率的实测映射；应分别报告传播变化及明确假设下的行为情景，不称为已测因果效应。
- **Q3 模块限制：**HVA 联合模型内部的行为组合可以使用，但其发声标记概率与独立计数模块的概率尚不相容。不得据两者直接拼接同一发声事件的联合概率或重复计数。详见 [Q3 输入说明](https://github.com/xurumu9/-apmcm-2026-c/blob/9a7e06f/experiments/reports/q3_release/Q4_FINAL_INPUT_NOTES.md)。
- **保护与实验：**建议在不同海况和噪声下重复传播与回放实验，记录声源、录音和个体标识以及响应人数；管理建议需注明物种、地点、季节、船舶活动和证据适用范围，不将示意模型阈值直接变成法定保护距离。

## 比赛规则与当前状态

[组委会 AI 使用规定](https://m.saikr.com/contest/notice_detail/50212)要求核心模型构建、算法设计与求解、结果分析由参赛队独立完成；AI 内容须标注，提交详细使用说明并核验。本文是 AI 辅助的现有结果整理，不是已由队伍独立完成的第四问模型，也未计算第四问综合半径、人数或噪声下行为变化。队伍需独立完成核心建模并复核此前 AI 辅助成果是否符合规定。
