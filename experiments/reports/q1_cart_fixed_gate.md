# CART 按日期误判与固定 F02 前置规则

2026-11-27 探索性分析。原 CART 的按日期留一组结果为 `[[42,2,0],[3,37,0],[3,0,21]]`（真实行、预测列顺序 flat/mod/tv），即 8 条误判。所有误判均未记录 PulseRate：2 条 flat 判 mod、3 条 mod 判 flat、3 条 tv 判 flat。三条 tv 的 F02 均有记录，且同在 2022-06-22 这个外层验证日期；该折树先根据 PulseRate 是否记录分叉，PulseRate 缺失时未再检查 F02。此分析描述当前数据及该折树，不证明测量缺失的原因。

按照用户此前提出的分层思路，以固定规则先处理 F02 有记录的样本为 tv，余下样本使用六个共同特征和 PulseRate 记录指示训练 CART；Gini，最大深度 3、叶节点最小 3，种子 42。按日期留一组，第二阶段各折只用训练日期拟合，折外混淆矩阵 `[[42,2,0],[3,37,0],[0,0,24]]`，准确率 103/108 = 95.37%，平衡准确率 95.98%，macro-F1 0.9602；6 条 PulseRate 缺失 mod 判对 3 条。

固定 F02 规则是检查同一数据及误判后的候选结构，其记录状态与 tv 标签完全对应，可能受到类别定义与测量流程影响。95.37% **不代表未知录音端到端的独立准确率**，亦不是该模型在独立数据上的无偏性能估计。日期不是个体 ID，六条困难 mod 太少；模型选择及结构调整均可能使结果偏乐观。此规则作为候选，须团队确认，并保留上述限制。

复现：`python src/python/q1_cart_fixed_gate.py`，依赖 NumPy、scikit-learn；输出本地忽略的 `results/q1/cart_fixed_gate_metadata.json`。运行 ID `q1_cart_fixed_gate_20261127T101007Z`（UTC）；Data01 SHA256 `1328f92601a84d81dbf8e1404fa0eeabc36cdf17a7626d9746aa62794827d02e`；脚本 SHA256 `8b6edec6ca229a43c2adf298a1f35bf070576d33ee7f36793bd1f3afce64b70c`，共享字段检查代码 SHA256 `9397127088976a90bf7fc546dc5e2af8cd091ed6ff8b57b2c19e896444a66222`。Git HEAD `582bb7c7d706129c8d235e1c32da3904bcf4d069`，脚本运行时未提交；Python 3.12.14、NumPy 2.5.5、scikit-learn 1.9.1。
