# 四问接口及运行说明

此文件记录合并后的共享接口。请在项目根目录执行以下命令；Python 依赖按各问的 README 和 `requirements-q3.txt` 安装。原始附件不随 Git 提交，需要从官方材料恢复至 `data/raw/`。具体结论与适用限制见四问报告及论文整合稿。

## 接口

| 衔接 | 共享内容 | 注意事项 |
|---|---|---|
| Q1 → Q2/Q3 | `flat`、`mod`、`tv` 类型和声学描述 | 实验之间没有确认的逐条录音键；不要按行合并，也不把 Q1 分类准确率作为响应概率。Q2/Q3 使用各自数据中的原类型。 |
| Q2 → Q4 | `experiments/reports/q2_2_descriptive_summary.csv`，按类型、指标和距离给出均值 | Q4 按 Q2 既定等权、等节点单调回归重建保真度；权重、阈值及噪声变化为情景假设，保真度不是识别概率。 |
| Q3 → Q4 | `experiments/reports/q3_release/q4_combination_original_flags_36.csv` | 以 Q3 八状态联合模型为唯一行为概率来源；H/V/A 编码，V 为播放后发声次数大于播放前，000 不代表未感知；保留支持标签。 |
| Q4 → 论文 | `results/q4/scenario_summary.csv` 和 `results/q4/gate_sensitivity.csv` | 输出为情景指标及假设人数，并非实测噪声响应或独立置信区间；结果目录默认不随 Git 提交。 |

Q4 对两份共享输入验证 SHA-256，若 Q2/Q3 更新数据，必须重新核对口径、计算和论文，而不能忽略哈希错误。`q4_scenarios.py` 读取当前仓库文件，不依赖其他分支的 Git 对象或联网。Q3 的行为标记模块与发声计数模块未建立一致的联合分布；Q4 不将它们拼成联合概率。Q3 的行为预测已经包括距离影响，Q4 叠加保真度为未经噪声数据标定的情景设定，可能重复计入部分距离影响。

## 核验与运行

1. 恢复 Data01、Data02 和 Data03–11 到 `data/raw/acoustics/`、`data/raw/playbacks/`、`data/raw/propagation/`；参见 `data/README.md`。
2. Q1 分类候选：`python -B src/python/q1_cart_fixed_gate.py`。输出到 `results/q1/`，重复运行会覆盖同名结果；分类依赖记录状态，不是独立未知音频测试。
3. Q2 数据及统计核验：`python -B src/python/verify_propagation_outputs.py`。需要原始 Data03–11 和仓库中的 Q2 汇总产物；若重跑 Q2 生成脚本，先查看各脚本的输出路径，避免覆盖团队已有输出。
4. Q3 聚合交付核验：`python -B src/python/q3_delivery.py verify`。这一步不要求原始数据，也不训练模型。测试可运行 `python -B -m unittest discover -s src/python -p 'test_q3*.py' -v`；完整测试需恢复 Data02 与科学依赖。完整重放还需要 Q3 私有的冻结中间结果和 Bootstrap 文件；先执行 `python -B src/python/q3_delivery.py check-context`，缺失材料时按 `docs/Q3_REPRODUCIBILITY.md` 从队内恢复，不能声称已完成 Q3 全部重放。
5. Q4 主计算：`python -B src/python/q4_scenarios.py`；再运行 `python -B src/python/q4_gate_sensitivity.py`；绘图可运行 `python -B src/python/q4_sensitivity_figure.py`。这些命令覆盖各自输出，绘图会更新 `figures/q4_sensitivity.png`。第四问的平滑主方案使用 Δ=0.1，其他宽度和硬门槛是对照。脚本检查输入哈希、HVA 完整性与概率和。

四问整合稿位于 `paper/latex/four_question_integrated_draft.md`，尚未成为排版完成的正式 PDF；参考文献、代表条件表、审阅和提交材料仍需整合。

## 2026-11-28 合并前验证记录

在隔离工作区恢复官方 Data01–11 后：Q1 声学检验、八特征表、CART 和记录状态敏感性运行成功，CART 为 103/108；Q2 核验 9 个源文件、18,900 个数据单元及 63 个汇总组通过；Q3 聚合交付 20 个文件的 SHA-256 检查通过，使用独立 Python 3.12.14 和 `requirements-q3.txt` 安装依赖后 11 项测试通过；Q4 两个计算脚本生成 4,860 条和 1,215 条记录，两个结果 CSV 均与合并前本地结果逐字节一致。Q1 和 Q2 使用 Python 3.11.14 环境；这些检查验证接口和复现，不能证明生态结论或未来表现。

Q3 `check-context` 仍提示缺少 23 项冻结中间文件；因此没有运行或声称完成 Q3 完整历史模型重放。第三问共享聚合结果可经哈希验证后直接供 Q4 使用；完整重放需由 P3 提供清单所列未上传材料。
