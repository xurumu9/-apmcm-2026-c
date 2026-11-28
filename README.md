# 2026 APMCM Problem C

非洲企鹅海上声学通信与回放响应建模项目。

研究链为：**声学特征与分类 → 传播保真度与范围 → 行为响应 → 通信效能与保护情景**。

当前状态：材料已归档并有模型实验记录；Q3 已完成阶段 1–4、阶段 5 的受限分析和阶段 6 区间交付，真实持续时间编码仍未核实。论文仍为工作模板，各问实际成果以研究报告为准，计划不代表完成。

## 项目导航

| 文档 | 用途 |
|---|---|
| [团队任务计划（统一入口）](docs/TEAM_PLAN.md) | 每项任务的工作、成员、截止日期和交付成果 |
| [总体研究框架](docs/PROJECT_PLAN.md) | 四问依赖与研究要求 |
| [数据接口](docs/TEAM_ROLES.md) | 已有格式与交付路径，不另列分工 |
| [模型决策记录](docs/MODELING_DECISIONS.md) | 候选模型、选择依据和假设 |
| [数据字典与审计](data/README.md) | 字段、缺失、冲突和处理状态 |
| [Q3 六阶段研究与验收](experiments/reports/q3_staged_implementation.md) | 各阶段实现、验证证据与仍未解决的问题 |
| [Q3 第一轮科学研究综述](experiments/reports/Q3_FIRST_ROUND_RESEARCH_SYNTHESIS.md) | [Response Pattern](experiments/reports/Q3_FIRST_ROUND_RESEARCH_SYNTHESIS.md#1-response-pattern)、[Response Intensity](experiments/reports/Q3_FIRST_ROUND_RESEARCH_SYNTHESIS.md#2-response-intensity)、[Response Latency](experiments/reports/Q3_FIRST_ROUND_RESEARCH_SYNTHESIS.md#3-response-latency)；模块接口与第二轮证据清单 |
| [Q3 第二轮研究方案](experiments/reports/Q3_SECOND_ROUND_RESEARCH_PLAN.md) | 数据/设计证据、三个科学模块、预定比较和分阶段执行要求 |
| [Q3 第二轮研究成果](experiments/reports/Q3_SECOND_ROUND_RESEARCH_SYNTHESIS.md) | R2-1～6实际交付、三模块科学回答、有限对照与Q4输入；保留固定基线，真实持续时间仍不可识别 |
| [Q3 最终研究综述与Q4接口](experiments/reports/Q3_FINAL_RESEARCH_SYNTHESIS.md) | 最新口径：Latency原标记278行为主，旧筛选为敏感性；发声概率跨模块不相容的诊断、语义与使用限制 |
| [Q3交付与复用](docs/Q3_REPRODUCIBILITY.md) | 依赖、测试、克隆后审核、冻结输入恢复和最终四步重放 |
| [Q4仓库共享接口](experiments/reports/q3_release/Q4_FINAL_INPUT_NOTES.md) | 可直接审阅的聚合预测、区间与限制，不依赖被忽略的本地results链接 |
| [Q3语义共享摘要](experiments/reports/Q3_DATA_SEMANTICS_SUMMARY.md) | 数据哈希与语义证据分级；原始逐行审计完整版仅本地保留 |
| [Q3 综合区间与 Q4 接口](experiments/reports/q3_uncertainty_delivery.md) | Bootstrap、未来预测范围、人口/支持与下游使用说明 |
| [GitHub 协作](GITHUB_WORKFLOW.md) | 可见性、分支和 PR |
| [Codex 工作规范](AGENTS.md) | AI 操作、验证与交付约定 |
| [AI 使用记录](AI_usage/README.md) | 关键交互、采纳与人工核验 |

三个人的任务及日期只在 [TEAM_PLAN.md](docs/TEAM_PLAN.md) 维护。

## 目录

- docs/：共享任务计划、研究框架、数据接口和模型决策。
- problem/：题面、补充说明和提交规范。
- literature/：后续查阅的论文、参考资料及来源记录。
- data/raw/：原始 CSV、音视频，保持原始内容和文件名。
- data/processed/：清洗、转换和特征工程产生的数据。
- src/reference_R/：题目附带的原始 R 参考脚本。
- src/python/、src/matlab/：队伍自行编写的代码。
- experiments/：实验方案、参数对比、验证记录。
- results/：模型输出、预测表、统计结果。
- figures/：论文使用的图表。
- paper/latex/：可编辑 LaTeX 工作副本；当前仍为原始模板。
- paper/templates/：原始 Word 模板及完整 LaTeX 模板归档。
- paper/build/：后续编译产物和提交版论文。
- AI_usage/：按本届比赛规定保留 AI 使用记录。
- file_manifest.csv：38 个原始文件的来源、归档位置、大小与 SHA256。

## 使用约定

所有路径以本目录为项目根目录。原始文件以复制方式归档，项目外的原始材料未修改或删除；本项目使用时不依赖外层目录。不要在 data/raw/ 上直接清洗或覆盖数据。

原始 R 脚本引用的 CSV 名称与附件实际名称不一致，且有未定义的模型对象；运行前应在新的工作脚本中调整路径并核对逻辑。归档脚本未修改、未运行。

LaTeX 工作副本的选题已设为 C，队号仍为占位符，正式写作前需要填写。模板自带的 PDF、日志等保留在 paper/templates/original_latex/。

AI 规定来源：https://m.saikr.com/contest/notice_detail/50212 （2026-11-04 发布，2026-11-26 核对）。

## GitHub 仓库范围

仓库上传项目框架、说明、自写代码和 LaTeX 工作源文件。原始附件、数据、音视频、原始参考脚本、模板归档、控制页、编译产物及本地文件清单已通过 .gitignore 排除，文件仍保留在本机。空目录用 .gitkeep 保留。

克隆后需要从正式比赛附件恢复原始材料，才能开展计算；本仓库初始提交不含模型实现和计算结果。

协作步骤见 [GITHUB_WORKFLOW.md](GITHUB_WORKFLOW.md)。不要填写或上传私钥、令牌、密码或签名承诺书。

## 开始研究

1. 查看 TEAM_PLAN.md 的任务与日期，并阅读对应研究方案和数据字典。
2. 恢复本地附件并统一审计规则，再实现基线。
3. 默认 Python，具体入口见 src/python/README.md 和各问实验报告；可靠 MATLAB 实现按共同 CSV 接口交付，实际依赖与版本记录在运行元数据。
4. 从最新 main 建任务分支，交付代码、实验记录、精简结果和章节说明，按需通过 PR 合并。

各问本地产物写入 results/q1/ 至 results/q4/，实际已生成版本以各问报告为准；供审阅的精简汇总和元数据放 experiments/reports/，不复制逐条原始记录。

实际仓库：[xurumu9/-apmcm-2026-c](https://github.com/xurumu9/-apmcm-2026-c)，保持 Private。

