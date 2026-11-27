# Q2 生成结果与共享范围

根据 P2 明确要求上传已完成工作，本分支对 `.gitignore` 作了**逐个文件的有限例外**：跟踪 `data/processed/propagation_long.csv` 和下列六个 Q2 结果文件。其他原始附件、结果及个人文件仍遵守原规则；没有使用 `git add -f`。

| 文件 | 内容 |
|---|---|
| `fidelity_grid.csv` | 三种叫声、两种候选模型、四组权重、4–256 m 整数距离上的估计。 |
| `communication_ranges.csv` | 阈值 0.3/0.5/0.7 的候选交点及边界状态。 |
| `candidate_distance_cv.csv` | 五个内部距离留一验证的观测、预测及误差。 |
| `noise_scenarios.csv` | 假设整体相似度下降时的情景，不是实测噪声效应。 |
| `missingness_extremes.csv` | 缺失值全为 0 或全为 1 时，观测综合均值的极端情景。 |
| `candidate_metadata.json` | 输入、脚本哈希、版本与模型参数。 |

`data/processed/propagation_long.csv` 由比赛原始表逐格转换，保留原始相关系数、文件名和来源行号；它不是原始附件文件，但可还原原始表的数值。**仓库在此次上传前核实为公开，以上文件及分支内容可被公开访问。**

结果均为 AI 辅助候选，尚需队伍核验。`lower`/`upper` 空表示统计置信区间未可靠估计，不是零；权重情景范围不是置信区间。不能将 AI 生成的核心模型、求解和分析声称为队伍独立完成。

运行方法与假设见 `experiments/reports/q2_candidate_notes.md`；完整情景与结果由 `python src/python/q2_candidate_models.py` 生成。图表和汇总在 `figures/q2/` 与 `experiments/reports/`。初期探索材料保存在 `experiments/archive/q2_first_draft/`，仅供追溯。
