# Q2 传播数据描述图：阶段记录

运行 ID：`q2_2_descriptive_v1`；运行日期：2026-11-27。对应 `TEAM_PLAN.md` 的 Q2-2 中三指标描述部分；**并未完成 Q2-2 的综合保真度、拟合比较与队伍判断**。

`src/python/propagation_describe.py` 读取 Q2-1 生成的 `data/processed/propagation_long.csv`，分别按叫声、指标、实测距离汇总有效数、缺失数、算术均值和样本标准差。输出 63 组精简统计 `q2_2_descriptive_summary.csv` 及图 `figures/q2/propagation_observed_means.png`；输入不修改，不使用原始行号进行跨文件连接。

图中的点是 4、8、16、32、64、128、256 m 七个实测距离的均值，横轴为线性距离；连线只是视觉引导，不是拟合曲线或中间距离的观测。为避免挤占版面，8 m、16 m 点有绘制但不单独列为横轴刻度。图不包含标准差或置信区间；各组样本标准差和有效数见汇总表。每组有效相关值数目 n 在 190–300 之间，不能将这些相互共享录音的相关值当成独立个体或独立叫声样例。不要将样本标准差视为置信区间。

## 复现与核验

- 基于 Q2-1 代码提交 `81e0fe0` 生成的长表；首先运行 `python src/python/propagation_audit.py`，然后运行 `python src/python/propagation_describe.py`。原始 Data03–11 须由队员在本地放入 `data/raw/propagation/`。
- 本次使用 Python 3.12.14、Matplotlib 3.11.2；Matplotlib 临时安装在工作区中，不包含在仓库。精确输入和本脚本 SHA-256 见 `q2_2_descriptive_metadata.json`；原始九文件的哈希在 `q2_1_audit_summary.json`。无随机过程。
- 单独复算并核对 63 组有效数、均值和标准差，检查输入和代码哈希；本地目视检查图像布局。该核对由 AI 执行，不等于队员人工审核。
- 作图及汇总不替代模型拟合、选择阈值、估计不确定性或解释声学意义。方法选择及结果分析需由队伍独立完成。
