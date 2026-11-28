# 第一问声学结果交接：供第二、三问参考

状态：2026-11-28，初步结果与跨问题讨论草稿，待队伍审阅。本文补充 Q2、Q3 已发布版本的结果，但不代表第一问论文已定稿或完成独立验证。

补充：八项声学特征统一结果表见 [完整特征表](q1_feature_table.md)；分层分类器的结构记录状态假设与情景分析见 [敏感性报告](q1_structure_sensitivity.md)。报告中的分类数值不代表识别概率或独立未知录音测试结果。

## 数据口径与可复现材料

Data01 有 108 条叫声：flat 44、mod 40、tv 24。Duration、F01、Fpeak、Q25、Q50、Q75 六个共同特征在三类中均有值。Duration 单位为秒，频率特征单位为 Hz；变量定义及来源见 [Data01 数据说明](../../data/README.md)及[原研究](https://doi.org/10.12688/openreseurope.24618.1)。原研究公开版本标注待同行评审。

- [声学描述和检验记录](q1_acoustic_tests.md)，代码为 `src/python/q1_acoustic_tests.py`；本地完整合并结果为 `results/q1/acoustic_results_table.csv`，候选图为 `figures/q1_fpeak_distribution.png`。
- [结构规则复现记录](q1_structure_rule.md)，代码为 `src/python/q1_structure_rule.py`。
- 输入文件 SHA256：`1328f92601a84d81dbf8e1404fa0eeabc36cdf17a7626d9746aa62794827d02e`。两个报告记录实际运行代码哈希、环境和验证方法；运行时脚本未提交。
- `results/` 和原始附件默认不进 Git：其他成员须从正式比赛附件恢复 Data01，再参考 `src/python/README.md` 运行代码。Git 上的报告与代码只有在实际提交、推送后才可访问。

## 供 Q2：传播退化与范围

| 已有结果 | 使用建议及边界 |
|---|---|
| Fpeak 三组中位数：flat 916 Hz、mod 831 Hz、tv 829.5 Hz；六个共同特征总体检验分别校正后，Fpeak 的 Kruskal–Wallis H=12.276、Holm p=0.01296。 | 可作为解释三类原始声学差异的背景；中位数有重叠，频率差异不等于传播距离差异。 |
| Fpeak 的 flat–mod 双侧秩和置换检验，在 18 项两两比较内 Holm 校正 p=0.01710，秩二列效应量 +0.409（flat 相对 mod 较高）。 | 可与分类型传播结果并列解释；不能将其直接作为传播模型的权重、相关系数或识别阈值。 |
| F01 的三组中位数分别为 298、287、274.5 Hz；六项总体检验 Holm p=0.05168。 | 可描述样本趋势；按本次校正口径不应称统计显著。 |

传播拟合使用 Q2 自己的 Data03–11 和既定声谱图、幅度谱、包络相关指标。Data01 的 Fpeak、频谱四分位频率与传播相关系数含义不同，不能直接替换或视为同一指标；不以不同实验文件的行号连接样本。Q2 的条件性结果及限制见下文。

## 供 Q3：回放行为

原研究依据声学结构区分 flat、mod、tv：F02 为第二基频，仅对 tv 记录；PulseRate 对存在幅度调制的叫声测量。Data01 中 flat 的 PulseRate 全缺失，mod 为 34/40 个有效值、tv 为 20/24；mod 和 tv 的其余缺失原因未逐条确认。类型可作为 Q3 的解释性分类变量，行为响应差异应由 Data02 实际估计；不能把未测量直接当零，或仅凭声学结构断定某类叫声的行为功能。

探索性结构规则“F02 有值→tv；否则 PulseRate 有值→mod；否则→flat”与 Data01 既有类别标签一致 102/108（94.4%），6 个 mod 判为 flat。该规则在了解同一表的标签和字段记录模式后提出；它不是独立测试或未知录音识别准确率。F02 和 PulseRate 的记录可能依赖原先分类或测量流程。Q3 不应把 94.4% 当作行为模型性能、响应概率或声学识别概率。

## 共同限制与后续对接

- Data01、回放和传播数据没有确认的逐条共同键，按类型、距离和情境整合，不按行连接；需要区分不同实验的样本单位。
- 声学检验是探索性结果：叫声来源个体未知，独立性及置换可交换性不能确认；未检出显著差异不等于两组完全相同。
- 本次两两比较的 p 值有蒙特卡洛误差；效应量、原始及校正 p 值见完整记录。资料中的原研究结果与本项目独立计算必须区分。
- Q2 和 Q3 均已有按类型汇总的结果，见下文；交付时应保留各自定义、样本量、假设和适用范围。

## Q1、Q2、Q3 衔接：供论文讨论与队友审阅

### 为后续模型选择声学指标

| 指标 | 选择理由 | 对现有 Q2、Q3 的实际用途 |
|---|---|---|
| CallType（基于声学结构的类别标签） | 第一问的分类目标，也是三个实验共有的分析维度。 | Q2 按类型拟合传播曲线；Q3 按类型比较回放响应。这是现有模型真正使用的共同接口。 |
| Fpeak | 三组共同测得；六项共同特征中，只有它的总体检验经 Holm 校正后低于 0.05，flat 与 mod 的两两比较也有差异。 | 描述各类初始频谱特征，为传播和回放结果提供声学背景；现有 Q2/Q3 并未直接将它作为连续输入。 |
| Q25、Q50、Q75 | 共同记录的频谱四分位数可概括能量在频率上的分布；不能仅因本次总体检验未显著就认定它们无传播意义。 | 作为频谱形状的补充描述，不能替代 Q2 实际使用的声谱图或振幅谱相关系数；现有 Q3 未将其作为连续协变量。 |
| PulseRate 与其记录状态 | 描述幅度调制；flat 全部未记录、mod 和 tv 分别有 34/40、20/24 个值。 | 可帮助解释类型的调制结构及包络分析的声学背景；与 Q2 的包络相关性并非同一变量，Q3 未使用其数值。缺失不得填零。 |
| F02 与其记录状态 | 第二基频在本表仅 tv 有记录，可描述两声部结构。 | 辅助解释 tv 类型与分类；不能把记录状态视为已经独立验证的声部检测器，亦不是现有 Q2/Q3 的连续模型输入。 |
| Duration、F01 | 三类均完整；分别描述时间尺度和第一基频。 | 保留为基本声学描述与分类候选；现有 Q2/Q3 未直接使用这两个连续变量。本次 F01 校正后 p=0.0517，不能称显著。 |

这些是根据特征含义、数据完整性和 Q1 分析给出的选择及解释，不是经证明的传播或行为预测变量重要性排名。题目要求选择后续指标；现有 Q2/Q3 实际直接采用的是类别而非这些 Data01 连续特征。由于实验间缺少确认的逐条录音映射，不将这些特征数值拼接进后续模型，也不声称已经检验了它们的独立效应。

下表并列不同实验和不同模型的结果，以声音类型为共同描述维度，不意味着观测记录逐条配对。Q2 取 `member2-propagation` 的提交 `6306e8e`；Q3 取 `p3/q3-final` 的提交 `9a7e06f`。两者的模型与结果均需队伍审核。

| 类型 | Q1：Data01 的 Fpeak 中位数 | Q2：等权、阈值 0.5 的模型交点 | Q3：相对对应海浪声对照，任一原行为标记的调整概率差 |
|---|---:|---:|---:|
| flat | 916 Hz | 89.90 m | 40.25 个百分点（95% 区间 28.84–52.34；30 对） |
| mod | 831 Hz | 150.47 m | 39.82 个百分点（95% 区间 27.08–53.29；20 对） |
| tv | 829.5 Hz | 180.10 m | 47.02 个百分点（95% 区间 36.26–57.71；39 对） |

Q2 使用三种相关指标等权综合、单调非增拟合及假设阈值 0.5；交点不是经过企鹅听觉实验验证的识别距离，排序也依赖模型、权重和阈值。原实验每类只有三个原始叫声样例，且在平静的内陆水域进行；所选权重情景范围不是统计置信区间。Q3 数值为各类型各自共同支持的配对人群中的调整差，区间为 expID 逐点 95% 区间；三个参考人群不同，不能据此直接比较类型优劣。原 V 标记表示播放后次数大于播放前，而非任意发声；三项原标记均为零不等于没有发声或行为。行为响应属于关联结果，不能直接说明叫声的信息内容或因果作用。

**供审阅的论文讨论草稿（中文）：**

> 三类叫声在声学结构上具有差异，且共同特征中的峰值频率在本样本中呈现组间差异。以六项共同特征的总体检验为一组进行 Holm 校正后，Fpeak 的组间检验 p = 0.01296；flat、mod 和 tv 的中位数分别为 916、831 和 829.5 Hz。基于另一传播实验，在三项相关指标等权、阈值为 0.5 的假设下，单调模型给出的保真度交点分别为 89.90、150.47 和 180.10 m。这一情景提示不同类型的声学结构可能伴随不同的传播表现，但由于实验样本无法逐条对应、权重和阈值属于假设，不能将距离差异归因于 Fpeak 或解释为实际识别距离。回放实验中，三类自然叫声相对各自海浪声对照均与更高的原行为标记出现概率相关，提示其具有与群体行为相关的潜在信息价值；不同类型使用的参考人群不同，不能据此直接比较其功能强弱，也不能由关联确定具体信息内容或因果机制。综合来看，声学特征、传播保真度与行为响应分别提供互补证据，三者之间的定量映射仍需共同录音标识及进一步验证。

**English discussion draft:**

> The three call types differ in acoustic structure. Among the six shared measurements, peak frequency showed a between-group difference after Holm correction (p = 0.01296), with medians of 916, 831, and 829.5 Hz for flat, modulated, and two-voice calls, respectively. In a separate propagation experiment, an equal-weight composite of three acoustic correlations, a non-increasing fit, and an illustrative threshold of 0.5 yielded crossings of 89.90, 150.47, and 180.10 m, respectively. These conditional results suggest differing propagation patterns, but the experiments cannot be linked record by record, and the crossings are neither measured recognition distances nor evidence that peak frequency causes the differences. In the playback analysis, each natural call type was associated with a higher probability of at least one original behavioural marker relative to its corresponding wave control. The reference populations differ across types, so the estimates do not establish a ranking of functions or identify the information conveyed by a call. Acoustic structure, propagation fidelity, and behavioural responses therefore provide complementary evidence; a quantitative link between them requires confirmed recording identities and further validation.

Q3 的行为标记与发声次数两个模型存在未修复的跨模块概率不相容；不得直接将两者概率相乘、相除来构造新的联合行为量。真实行为持续时长不可识别；部分条件时间缺少直接观测支持。以上讨论未使用或修复这些缺口，也不将概率当作响应人数。

来源：[Q2 工作稿](https://github.com/xurumu9/-apmcm-2026-c/blob/6306e8e/experiments/reports/q2_working_section_en.md)、[Q2 范围审查](https://github.com/xurumu9/-apmcm-2026-c/blob/6306e8e/experiments/reports/q2_scope_review.md)、[Q3 最终综述](https://github.com/xurumu9/-apmcm-2026-c/blob/9a7e06f/experiments/reports/Q3_FINAL_RESEARCH_SYNTHESIS.md)、[Q3 接口说明](https://github.com/xurumu9/-apmcm-2026-c/blob/9a7e06f/experiments/reports/q3_release/Q4_FINAL_INPUT_NOTES.md)。本文为 AI 辅助整合草稿，数值引用已有报告，未重新运行 Q2/Q3；队伍应检查计算、解释及比赛 AI 使用规则后决定采用与披露方式。
