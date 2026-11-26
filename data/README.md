# 数据说明

| 位置 | 文件 | 结构 |
|---|---|---|
| raw/acoustics/ | Data01 | 108 行 × 11 列；flat 44、mod 40、tv 24 |
| raw/playbacks/ | Data02 | 278 行 × 40 列；139 个 expID，每组自然叫声与对照各一条 |
| raw/propagation/ | Data03–11 | 每份 300 行 × 7 列；4、8、16、32、64、128、256 m |
| raw/media/ | Supplementary2、5 | 1 个实验视频、3 段示例音频 |

## 建模前待核对

- F02 仅 tv 有值；flat 的 PulseRate 全缺失，不能统一填零。
- 回放记录应保留 expID 的组内相关性；同组播放距离可以不同，expID 42、66 的 Npenguins 也不同。
- VocalYesNo=0 但有潜伏期和正发声次数：expID 34、80（control），136、160（call）。
- ApproachYesNo=0 但有潜伏期：expID 25、53、80、129、130（call）。
- 无响应潜伏期不能填成 0；删失分析前需核实观察窗口。
- 传播数据存在缺失且没有显式样本 ID，不能未经确认就将行视为独立样本或跨文件配对。
- Npenguins 是观察数量，不能直接当作实际响应人数；其中位数为 8。

本次仅检查原始数据，未清洗、插补、拟合或更改原值。详细字段解释以题面和补充材料为准。
