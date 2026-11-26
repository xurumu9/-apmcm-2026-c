# 数据接口约定

本文件保留既有数据格式和交付路径，不再承担团队分工；唯一任务计划见 [TEAM_PLAN.md](TEAM_PLAN.md)。文件名保留以兼容现有引用。

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

| 本地路径 | 最低内容 |
|---|---|
| data/processed/audit_issues.csv | source_file、source_row_id/exp_id、字段、问题、证据、处理规则、状态 |
| data/processed/acoustics_clean.csv | 来源行号、类型、日期、地点、声学特征、缺失/质控标记 |
| data/processed/playbacks_clean.csv | 来源行号、exp_id、context、call_type、distance_m、n_penguins、原行为值、分析值、规则版本 |
| data/processed/propagation_long.csv | call_type、metric、distance_m、source_row_id、correlation、缺失标记；行号不代表跨文件配对 |
| results/q1/feature_summary.csv、classification_metrics.csv | 特征统计、n、检验及校正、效应量、折外指标和验证设置 |
| results/q2/fidelity_grid.csv | call_type、distance_m、scenario、estimate、lower、upper、weight_scheme、区间方法 |
| results/q2/communication_ranges.csv | 类型、scenario、threshold、recognition_state、radius_m、lower、upper、status |
| results/q3/combination_predictions.csv | 类型、情境、距离、群体规模、combo、probability、lower、upper |
| results/q3/latency_intensity_predictions.csv | 代表条件、behavior、outcome、response_probability、条件潜伏期/强度、单位、区间、status |
| results/q4/scenario_summary.csv | 类型、情境/权重、距离、规模、scenario、指标版本、效能/半径/人数估计及区间 |

## 数据使用说明

检查单位、范围、样本量和版本，不拼接不同规则或情景的无标识产物。异常保留原值并记录依据；模型有真实验证证据才称为采用。完整产物经队内私有渠道传递，Git 保留代码、研究记录和精简汇总。
