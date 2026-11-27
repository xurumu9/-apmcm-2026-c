# 第一问：声学差异分析复现记录

- 运行 ID：`q1_acoustics_20261127T035734Z`（UTC）。
- 输入：Data01，SHA256 `1328f92601a84d81dbf8e1404fa0eeabc36cdf17a7626d9746aa62794827d02e`；代码 `src/python/q1_acoustic_tests.py`，SHA256 `64ae12e8c807d34f3191caccf689cb707c59214174b6f4f42dee40a2638711cf`。Git HEAD 为 `7e7a6c01d3a3298ac5ca3959afd0c948a13ace06`；脚本运行时尚未提交，HEAD 不代表此文件版本。
- 环境：Python 3.12.14、NumPy 2.5.5、SciPy 1.18.1、Matplotlib 3.11.2。未修改原数据，缺失不填零；四分位数按线性插值。
- 统计：三组 Kruskal–Wallis 检验六项；所有特征的两两双侧秩和置换检验共 18 项，种子 20261127，每项 20,000 次，p 值按加一修正。两族 p 值分别做 Holm 校正。
- 局限：本次为探索性结果；个体身份未知，样本独立性与置换可交换性尚不能确认。置换 p 值有蒙特卡洛误差。无结果应解释为声学原因或生态因果结论。

## 样本特征和总体检验

表中数据为中位数（Q1–Q3）；flat、mod、tv 的 n 分别为 44、40、24。Duration 单位为秒，其余特征单位为 Hz；单位依据[原研究](https://doi.org/10.12688/openreseurope.24618.1)。

| 特征 | flat | mod | tv | H | Holm p |
|---|---:|---:|---:|---:|---:|
| Duration | 0.3672 (0.3150–0.4315) | 0.3938 (0.3489–0.4456) | 0.3833 (0.3435–0.4620) | 2.523 | 0.8497 |
| F01 | 298 (266.75–310) | 287 (271.5–298.5) | 274.5 (263.75–282) | 9.144 | 0.0517 |
| Fpeak | 916 (825.5–964.25) | 831 (285–906.75) | 829.5 (296–912.75) | 12.276 | 0.0130 |
| Q25 | 537.5 (468–622.25) | 501 (460.25–557.25) | 495 (407–587.25) | 2.157 | 0.8497 |
| Q50 | 908 (825.5–937) | 864.5 (821.5–900) | 844.5 (826.75–891.5) | 6.425 | 0.1610 |
| Q75 | 1099 (986–1195.75) | 1097.5 (1030.25–1151) | 1083 (1018.25–1118.75) | 0.520 | 0.8497 |

六项总体检验中，只有 Fpeak 的 Holm 校正 p 值低于 0.05；F01 为 0.0517，不能在该口径下报告为显著。

## 两两比较与图

Fpeak 的 flat 与 mod 比较：双侧秩和置换 p=0.000950，18 项 Holm 校正 p=0.017099，秩二列效应量 `2U/(n1*n2)-1` 为 +0.409；正号代表 flat 倾向高于 mod。Fpeak 的 flat 与 tv 校正 p=0.158392、效应量 +0.379；mod 与 tv 校正 p=1.000000、效应量约 -0.009。全部 18 项结果和效应量在本地 `results/q1/acoustic_pairwise_permutation.csv`；包含各组分位数及所有比较结果的合并表为 `results/q1/acoustic_results_table.csv`。

候选图为 `figures/q1_fpeak_distribution.png`。英文图注建议：**Distribution of peak frequency by call type. Points represent individual calls; boxes show the interquartile range, center lines indicate medians, and whiskers extend to observations within 1.5 times the interquartile range.** 图仅为候选，是否纳入论文由团队决定。

F02 仅在 tv 中有值；PulseRate 在 flat 中无值，mod 有 34 个有效值，tv 有 20 个。此处不对这两个变量机械执行三组总体检验。团队后续可依据问题需求讨论 mod 与 tv 的脉冲率比较，但不将其混入本次预先定义的检验族。
