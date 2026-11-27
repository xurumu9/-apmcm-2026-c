# 传播相关性的离散程度图：阶段记录

运行 ID：`q2_dispersion_v1`；运行日期：2026-11-27；基于提交 `3572a07` 中 63 组描述性汇总。代码提交以 Git 历史为准，输入与脚本 SHA-256、Python 和 Matplotlib 版本见 `q2_dispersion_metadata.json`。不使用随机数。

图 `figures/q2/propagation_mean_sd.png` 按叫声类型和声学指标分为九个面板。横轴以 log₂ 刻度显示 4、8、16、32、64、128、256 m；每个点是对应组的相关系数算术均值，竖线是均值 ± 一个样本标准差。各面板标题中 n 为七个距离上有效相关值数量的最小值至最大值，不是独立企鹅或独立原始叫声的数量。每个距离的确切 n、均值和标准差可见 `q2_2_descriptive_summary.csv`。

该图不拟合模型、不表示识别概率、不显示置信区间。相关值共享录音，标准差只描述当前相关值的离散程度，不提供模型参数或通信距离的统计置信区间。不同指标也不能凭行号作配对。

## 复现与核对

在已有 Data03–11 的本地工作副本和 Matplotlib 的情况下，依次运行 `python src/python/propagation_audit.py`、`python src/python/propagation_describe.py`、`python src/python/propagation_dispersion.py`。程序读取 63 组汇总，输出图和元数据，不修改原始数据。本次为 Python 3.12.14、Matplotlib 3.11.2。

检查包括：63 组唯一性、相关性均值与标准差取值范围、七个距离、输入和脚本哈希；额外使用临时文件验证重复组被拒绝，并目视检查图表。检查由 AI 执行，人工核验及论文使用决定尚待队员完成。
