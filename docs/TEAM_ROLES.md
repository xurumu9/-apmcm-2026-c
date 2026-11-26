# 三人职责与模块交付接口

P1/P2/P3 是人类成员代号，不是自动化代理。以下为默认分工，待队内确认后可通过 PR 调整。

| 成员 | 主责 | 主要范围 | 审阅人 |
|---|---|---|---|
| P1 | 数据审计、统一清洗、Q1 声学与分类 | src/python/data/、src/python/q1/、数据字典、审计和 Q1 实验 | P2 |
| P2 | Q2 传播、Q4 效能整合与噪声情景 | src/python/q2/、src/python/q4/、传播与情景实验 | P3 |
| P3 | Q3 行为、论文统稿、图表引用与提交清单 | src/python/q3/、paper/latex/、行为和论文核查记录 | P1 |

各自交付对应章节与图注，P3 统一结构而不替代他人验证。跨模块接口及综合主结论三人共同确认。实际赛事提交人待队内指定。

Python 为默认整合语言；可靠 MATLAB 实现可放 src/matlab/，以同样 CSV 接口交付，避免重复实现。R 实现另记依赖和入口。模块目录按需建立。

## 统一格式

- CSV 为 UTF-8，无额外索引列；snake_case 列名；缺失留空，不填零。
- call_type=flat/mod/tv，仅行为表允许 control；context=commuting/searching/after。
- distance_m 单位米；时间单位核实后才用 latency_s/duration_s。未知单位不猜测。
- combo 按 HVA 顺序，H=抬头、V=发声、A=接近；000–111，000 为无响应。
- metric=spectrogram/amplitude_spectrum/envelope。
- estimate/lower/upper 说明估计量与区间方法；计划默认 95% 区间，变更时注明。
- 不可估计用缺失加 status，不伪造零；同条件下组合概率求和为 1。
- 每项输出附 run_id、代码提交、输入哈希、清洗版本、参数、种子、依赖与验证方式。

## 计划交付契约

以下产物尚未生成。变更文件名或字段须更新契约并通知下游。

| 主责 → 使用方 | 本地路径 | 最低内容 |
|---|---|---|
| P1 → 全员 | data/processed/audit_issues.csv | source_file、source_row_id/exp_id、字段、问题、证据、处理规则、状态 |
| P1 → P1 | data/processed/acoustics_clean.csv | 来源行号、类型、日期、地点、声学特征、缺失/质控标记 |
| P1 → P3 | data/processed/playbacks_clean.csv | 来源行号、exp_id、context、call_type、distance_m、n_penguins、原行为值、分析值、规则版本 |
| P1 → P2 | data/processed/propagation_long.csv | call_type、metric、distance_m、source_row_id、correlation、缺失标记；行号不代表跨文件配对 |
| P1 → P2/P3 | results/q1/feature_summary.csv、classification_metrics.csv | 特征统计、n、检验及校正、效应量、折外指标和验证设置 |
| P2 → P3/Q4 | results/q2/fidelity_grid.csv | call_type、distance_m、scenario、estimate、lower、upper、weight_scheme、区间方法 |
| P2 → P3 | results/q2/communication_ranges.csv | 类型、scenario、threshold、recognition_state、radius_m、lower、upper、status |
| P3 → P2 | results/q3/combination_predictions.csv | 类型、情境、距离、群体规模、combo、probability、lower、upper |
| P3 → P2/论文 | results/q3/latency_intensity_predictions.csv | 代表条件、behavior、outcome、response_probability、条件潜伏期/强度、单位、区间、status |
| P2 → P3 | results/q4/scenario_summary.csv | 类型、情境/权重、距离、规模、scenario、指标版本、效能/半径/人数估计及区间 |

## 验收与冲突

交付人检查结构、单位、范围、样本量和版本；下游不得拼接不同规则/情景的无标识产物。异常保留原值并登记，主责与审阅人确认分析口径。模型有真实验证证据才标为采用。

成员先交付章节，P3 整合主文件；不同时覆盖 main.tex，不用整文件覆盖解决他人修改冲突。完整产物经队内私有渠道传递，Git 留代码、实验记录和精简汇总。
