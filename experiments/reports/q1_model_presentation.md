# 第一问：分类模型和对照的论文表述（候选）

## 本轮候选及比较口径

本轮以用户倾向的“F02 记录状态前置 + flat/mod CART”作为论文候选，保留仅六个共同特征的基线、直接结构规则和不确定状态作为对照。当前数据已用于多轮探索和模型选择，以下结论不表示最终方法经团队采纳，也不表示有独立测试数据。

| 方法 | 输入及结果 | 验证性质与边界 |
|---|---|---|
| 六共同特征浅随机森林 | Duration、F01、Fpeak、Q25、Q50、Q75；accuracy 44.4%、macro-F1 0.399 | 采用现有 [共同特征报告](q1_common_feature_baselines.md) 的按日期留组结果；无结构状态输入，作为不同输入条件的参考。 |
| 直接结构规则 | F02 有值→tv；否则 PulseRate 有值→mod；否则→flat；102/108 = 94.4%，κ≈0.914 | 同表规则一致率，规则在观察这份数据后提出，不是独立测试或音频识别准确率。 |
| 固定 F02 前置 + CART | F02 有值→tv；其余用六共同特征和 PulseRate 记录指示；103/108 = 95.37%，macro-F1≈0.960 | CART 第二阶段按日期留组折外；前置规则和结构在看过同一数据后确定，依赖结构记录可用。不能称独立测试或泛化准确率。 |
| 待判规则 | F02 有值→tv；否则 PulseRate 有值→mod；其余待判；58/108 覆盖，其中 58/58 与现有标签一致 | 同表状态对照，不是概率校准；44 条 flat 均待判，不能代替完整三分类。 |

上述输入及验证性质并不相同，不能按百分比把候选排序为未经偏差校正的最优方法，也不能将含结构记录状态的结果解释为仅由六个共同声学特征实现。

## 候选方法说明

首先读取 F02 是否有记录；有记录时按数据口径判为 tv。否则将六个共同特征及 PulseRate 是否记录输入二类 CART，输出 flat 或 mod；CART 为 Gini、最大深度 3、最小叶节点 3，训练/验证按日期留组。六个特征允许进入树模型，并不代表每个折都会使用所有特征。具体参数、矩阵、输入及代码哈希见 [固定门控实验](q1_cart_fixed_gate.md)。

候选混淆矩阵按真实行、预测列 flat/mod/tv 为 `[[42,2,0],[3,37,0],[0,0,24]]`；flat、mod、tv 的召回分别为 42/44、37/40、24/24。6 条 PulseRate 缺失的 mod 有 3 条识别正确。日期不是企鹅个体 ID；此前已反复比较候选，模型门控和结构是事后确定，不可称为独立测试或无偏泛化性能。

结构记录状态与类别定义/测量流程可能相关：一旦对未知录音无法独立确认 F02 或 PulseRate，规则无法按原条件使用，也不能将数据表中的 95.37% 套用到自动音频识别。见 [结构状态敏感性](q1_structure_sensitivity.md)：以测试指示量翻转为假设，描述结论受输入状态变化的影响；情景概率并非实测检测错误率，未模拟训练误差或个体聚类。

## 英文方法与限制表述草稿

> We explored a two-stage classifier under the availability of the recorded structural indicators. A call with a recorded second fundamental frequency was assigned to the two-voice class; otherwise, a CART model used the six common acoustic measurements and the pulse-rate recording indicator to distinguish flat from modulated calls. In leave-one-date-out evaluation of the CART stage, combined with the fixed structural rule, 103 of 108 records agreed with their labels. The structural rule and model were selected after exploratory analysis of the same dataset. Recording status may reflect the original classification or measurement process; consequently, this result is conditional on the supplied indicators and does not establish performance on independently collected audio.

此段落是候选草稿，需由队伍按真实研究过程和比赛 AI 使用规定审阅与修改。报告中应同时保留三个类别的混淆矩阵和困难 mod 的结果，而不是只突出总体百分比。

## 第一问论文正文草稿（英文，供队伍修改）

### Acoustic characteristics and statistical comparison

Data01 contains 108 calls: 44 flat, 40 modulated and 24 two-voice. We summarized duration, first and second fundamental frequencies, peak frequency, spectral quartiles and pulse rate by call type using medians and interquartile ranges (see the full feature table). The six measurements available for all three classes are duration, F01, Fpeak, Q25, Q50 and Q75. F02 was recorded only for the 24 two-voice calls. Pulse rate was recorded for 34 of 40 modulated and 20 of 24 two-voice calls, and was not recorded for flat calls. Missing records were retained as missing rather than set to zero.

For the six shared measurements, we used the Kruskal–Wallis test to compare the three call types and adjusted the six overall p-values using Holm's method. We also performed two-sided pairwise rank-sum permutation tests, using 20,000 permutations per comparison, with a separate Holm correction across the 18 feature-by-pair comparisons. Peak frequency differed among the three types (H = 12.276, adjusted p = 0.01296); its medians were 916, 831 and 829.5 Hz for flat, modulated and two-voice calls. The flat–modulated pair had an adjusted permutation p-value of 0.0171 and rank-biserial effect size of 0.409, indicating a tendency towards higher values for flat calls. F01's overall adjusted p-value was 0.0517; the remaining shared measurements did not reach the 0.05 threshold in this family. Lack of significance does not imply identical distributions. F02 and pulse rate were not subjected to a three-group test because their availability differs by type. Individual identities and independence are not confirmed, so these tests are exploratory.

### Classification

We explored a two-stage classifier conditional on the recorded structural indicators. Records with F02 present were assigned to the two-voice class; the remaining records were classified as flat or modulated by a CART tree using the six shared measurements and an indicator of whether pulse rate was recorded. The CART used Gini impurity, maximum depth 3 and minimum leaf size 3. Its second stage was evaluated by leaving out each recording date in turn and fitting on the remaining dates. Combining these predictions with the fixed first-stage rule gave 103 correct labels out of 108 (95.37%), with macro-F1 0.960. The confusion matrix, with true classes as rows and predicted classes as columns in flat, modulated, two-voice order, was [[42, 2, 0], [3, 37, 0], [0, 0, 24]]. Of six modulated calls without a pulse-rate record, three were classified correctly.

The first-stage rule and model structure were chosen after examining the same data; F02 and pulse-rate recording may also reflect the original measurement or labeling process. Thus the reported result is conditional on those records and is not an independent estimate of performance on new audio. Date is not an individual identifier, and repeated exploration can make the observed performance optimistic. A six-shared-feature-only baseline and a sensitivity analysis for structural-record availability are reported separately; their different inputs and evaluation designs must be retained when comparing results.

### Feature selection and connection to propagation and playback

Call type is the common categorical interface used in the existing propagation and playback models. Fpeak is retained as a shared frequency descriptor with observed between-type differences; Q25, Q50 and Q75 provide complementary summaries of spectral distribution. Pulse rate and F02 help describe modulation and two-voice structure, subject to their type-dependent availability. Duration and F01 remain useful descriptive and classification candidates. These continuous Data01 measurements were not directly included in the existing Q2 or Q3 models, and their selection does not establish feature-specific effects on propagation or behavior.

Under Q2's equal-weight fidelity composite and illustrative threshold 0.5, the fitted crossings were 89.90, 150.47 and 180.10 m for flat, modulated and two-voice calls, respectively. The result depends on the assumed model, weights and threshold and is not a measured recognition distance. In Q3, the estimated probability of at least one original behavior marker was higher for each natural call than for its corresponding wave control. The three type-specific reference populations differ, preventing a direct ranking of their functions from those estimates. The experiments do not have confirmed record-level links; consequently, the observed differences provide complementary descriptions rather than evidence that a specific acoustic feature causes a propagation or behavioral difference. See the [cross-question handoff](q1_handoff_q2_q3.md) for estimates, assumptions and source versions.

**排版交接：**特征统计使用 [完整特征表](q1_feature_table.md)；八项指标的分布图为 [声学特征图](../../figures/q1_acoustic_features.png)，可由 `python src/python/q1_feature_figure.py` 重现；分类混淆矩阵可用上文数据制作论文表。建议图注：*Acoustic measurements by call type. Points are individual recorded values; boxes show the interquartile range and medians, with whiskers extending to observations within 1.5 interquartile ranges. Sample sizes refer to recorded values; n=0 indicates no recorded measurements.* 图注、表格编号和引用须与团队最终论文统一。
