# 第一问：结构判别规则

`q1_structure_rule.py` 计算 Data01 上结构判别规则与既有类别标签的一致情况。它只依赖 Python 标准库，不会修改原始数据。

在项目根目录运行：

```powershell
python src/python/q1_structure_rule.py
```

如果 `python` 未加入 PATH，请使用本机 Python 3 的可执行文件运行同一脚本。输入是 `data/raw/acoustics/Data01_AfricanPenguins_seasurface_calls_acoustics.csv`；须从比赛附件恢复。输出为 `results/q1/structure_rule_confusion.csv` 和 `results/q1/structure_rule_metadata.json`，重复运行会覆盖这两个规则结果文件。结果目录按项目约定不随 Git 提交。

规则：F02 有值判为 tv；否则 PulseRate 有值判为 mod；否则判为 flat。数值只用于判断是否记录，原值不变。空字符串、NA、NaN 和 null 视为缺失，其他非数值或非有限值会报错。

**这是探索性表内一致率，不是独立测试准确率。** 类别定义、测量和记录流程可能使字段是否有值包含类别信息。对于未知录音，无法从现有结果得知双声部或脉冲是否能独立、正确地检测；PulseRate 缺失也不必然等于没有脉冲。运行记录包括输入和脚本 SHA256、运行时间、Git HEAD 和环境；脚本尚未提交时，以脚本哈希识别实际运行版本。

原研究对 F02 和 PulseRate 的定义见 [Thiebault 等](https://doi.org/10.12688/openreseurope.24618.1)。规则来自用户提供的参考材料，须按比赛规则处理来源和 AI 使用记录。

## 声学特征描述与非参数检验

`q1_acoustic_tests.py` 生成六个共同特征的描述统计、三组 Kruskal–Wallis 检验、18 项两两秩和置换检验，以及 Fpeak 候选图。输入为同一份 Data01；脚本不修改原始数据。需要 NumPy、SciPy 和 Matplotlib；本次实际运行版本分别为 2.5.5、1.18.1、3.11.2，Python 3.12.14。

```powershell
python src/python/q1_acoustic_tests.py
```

脚本将 `feature_summary.csv`、`acoustic_kruskal_wallis.csv`、`acoustic_pairwise_permutation.csv`、`acoustic_results_table.csv` 和运行元数据写入本地忽略的 `results/q1/`，候选图写入 `figures/q1_fpeak_distribution.png`。重复运行覆盖同名文件。汇总表的秩二列效应量正值表示 group_1 倾向于大于 group_2；区间为空不是零。脚本固定置换和图形抖动的随机种子为 20261127；置信区间未计算。

总体检验六项与两两比较十八项分别进行 Holm 校正；两两检验为双侧秩和置换，20,000 次、p 值加一修正。调用 Kruskal–Wallis 的卡方近似；检验的独立性和置换可交换性尚无法由现有字段确认。图中箱体为四分位距，中线为中位数，须为 1.5 倍四分位距内最远观测值，点为各观测值。单位取自[原研究](https://doi.org/10.12688/openreseurope.24618.1)。

## 两阶段加权模型候选

`q1_weighted_classifier.py` 以 F02 记录状态识别 tv，再以六个共同特征、PulseRate 和 PulseRate 记录状态作 flat/mod Logistic 回归；每个训练折内完成填补与标准化。需要 NumPy、SciPy、scikit-learn，本次版本分别为 2.5.5、1.18.1、1.9.1。运行 `python src/python/q1_weighted_classifier.py`，结果写入本地忽略的 `results/q1/weighted_classifier_metadata.json`，重复运行覆盖该文件。完整方法、指标和结构信息导致的限制见 `experiments/reports/q1_weighted_classifier.md`。该模型目前未改善困难样本，非最终采纳结论。

## flat / mod 特征比较

运行 `python src/python/q1_flat_mod_features.py`，使用 NumPy、SciPy 比较六个共同特征的分布及秩二列效应量，计算渐近 Mann–Whitney 检验和按日期限制的标签置换检验。运行结果写入本地忽略的 `results/q1/flat_mod_feature_comparison.csv` 和元数据；重复运行覆盖同名文件。方法和独立性限制见 `experiments/reports/q1_flat_mod_features.md`。

## 待判规则对照

`python src/python/q1_selective_classification.py` 对照完整结构规则与“两项结构指标均未记录则待判”的规则，报告整体及各类覆盖率和覆盖样本的一致率。仅依赖标准库，并引用同目录的 `q1_structure_rule.py`；结果写入本地忽略的 `results/q1/selective_classification_counts.csv` 和元数据，重复运行会覆盖。待判规则未判定任何 flat，不能当作完整三分类器；两种规则均为同表探索，不能解释为未知音频的准确率。详见 `experiments/reports/q1_classification_comparison.md`。

## CART 候选分类器

`python src/python/q1_cart_classifier.py` 使用六个共同声学特征及 F02、PulseRate 记录指示，运行最大深度 3、叶节点最少 3 个样本的 CART，并报告按日期留一组及随机分层五折结果，输出本地忽略的 `results/q1/cart_classifier_metadata.json`。依赖 NumPy 与 scikit-learn，调用同目录 `q1_structure_rule.py` 的原始字段检查；结构记录指标的类别信息风险、模型选择和未知音频验证限制见 `experiments/reports/q1_cart_classifier.md`。

`python src/python/q1_cart_feature_comparison.py` 对比共同特征、推导的频率比和带宽、条件记录数值的候选集合，同时进行外层按日期留一组和内层按日期分组的模型选择。结果写入本地忽略的 `results/q1/cart_feature_comparison_metadata.json`；方法、平分时优先级及限制见 `experiments/reports/q1_cart_feature_comparison.md`。依赖 NumPy 与 scikit-learn。

`python src/python/q1_cart_fixed_gate.py` 验证先用 F02 记录状态判断 tv，再用 CART 判断 flat/mod 的探索方案。结果写入本地忽略的 `results/q1/cart_fixed_gate_metadata.json`；其结构规则在查看同一数据及误判后固定，且依赖 F02 记录状态，不能解释为未知录音的独立准确率，详见 `experiments/reports/q1_cart_fixed_gate.md`。

## 完整特征表和结构信息敏感性

先运行 `q1_acoustic_tests.py`，再运行 `q1_feature_table.py`，汇总八个特征的分位数、有效与缺失数量及适用的检验；会校验现有统计结果与输入和代码版本。`q1_cart_fixed_gate.py` 生成基线后，运行 `q1_structure_sensitivity.py`，枚举测试阶段结构记录指示被翻转的假设情景；各项翻转概率不是实测检测错误率。详细边界、运行版本及输出见 `experiments/reports/q1_feature_table.md` 和 `experiments/reports/q1_structure_sensitivity.md`。这些脚本输出本地忽略的 `results/q1/` 下对应文件，重复运行会覆盖同名结果。
