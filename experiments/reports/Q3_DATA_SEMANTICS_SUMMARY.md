# Q3原始数据语义：仓库共享摘要

2026-11-28。完整只读审计在本地`Q3_DATA_SEMANTICS_EVIDENCE.md`，含26行全字段原始快照，按仓库共享约定不上传。本摘要不复制逐条原始记录，不替代作者的标注手册。

## 已确认

- 本地Data02与[Zenodo公开CSV](https://zenodo.org/api/records/21376649/files/Data02_AfricanPenguins_playbacks_data.csv/content)逐字节一致，278行×40列、28879字节，SHA-256为`1480671419ace67d8e94d819c758f2954550a7a40cba92ad43fd9ffa392a61a5`。
- 本地作者R与公开文件逐字节一致，34899字节，SHA-256为`912044aaff0f76c8971f348031558da29edd87aa76f045ff135d9d2a3d7739db`。来源一致不证明每条原始标注正确。
- 全278行满足`VocalYesNo=I(N_after>N_before)`，且`VocalRelNCalls=max(N_after-N_before,0)`。实际正次数85，原V标记81，四条差异有记录发声时间且播放后次数小于播放前。
- 五条Approach原标记为0却有Latency，Duration/RelDist为0；H有九条记录零潜伏期。不能在语义未确认时直接更改或删除。
- 十行有11个Duration=60行为项，其中10项的Latency+Duration超过论文窗口。60编码未确认，真实持续时间不识别。
- 自然轨道28个：11 Flat、7 Mod、10 TV；Control另计1个。论文方法写9 Flat，R和补充模型的29个含Control层级支持数据口径；差异只定位于Flat，不能任选两ID删除。
- 论文说明同群体配对及随机顺序，群体间的隔离安排不证明同一配对的实际间隔/洗脱。
- 补充视频、PDF和三段叫声示例已在本地保存；不是全量逐实验录像/录音或28个刺激映射。

来源：[原论文](https://ore.eu/article/view/1538/version/2510)、[Zenodo文件元数据](https://zenodo.org/api/records/21376649/files)、[作者R](https://zenodo.org/api/records/21376649/files/Code1_AfricanPenguins_playbacks_analyses.R/content)。

## 仍需区分的推测与作者问题

字段函数关系已确认，作者是否有意按相对增加标记V仍待核实。Duration的60是否为精确时间、结束标记或删失值；H/A整数与零的精度；Approach判定阈值；原始录音身份映射；配对内实际顺序/间隔都不能由拟合得分确定。没有联系作者或修正原数据。

最新主分析采用278行原标记，旧排除人口为敏感性。Vocal累计量表示最终满足原标记且记录时间≤t，不能称首次超过基线时间；计数N>0独立建模。科学结果、跨模块不相容和Q4使用限制见[最终综述](Q3_FINAL_RESEARCH_SYNTHESIS.md)及[可直接审阅的聚合接口](q3_release/Q4_FINAL_INPUT_NOTES.md)。
