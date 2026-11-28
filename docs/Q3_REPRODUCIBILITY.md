# Q3交付与复用说明

本次正式提交为研究代码、英文论文片段及约1.37MB聚合审核材料。正式口径见[最终综述](../experiments/reports/Q3_FINAL_RESEARCH_SYNTHESIS.md)，Q4直接阅读[共享接口说明](../experiments/reports/q3_release/Q4_FINAL_INPUT_NOTES.md)及[共享清单](../experiments/reports/q3_release/q4_final_input_manifest.csv)。没有修改模型路线或重跑既有实验。

## 1. 刚克隆后：不需要原始数据即可审阅

在项目根目录用Python 3.12运行：

```powershell
python -B src/python/q3_delivery.py verify
```

该命令只依赖标准库，核对`experiments/reports/q3_release/release_manifest.json`中20项共享文件的SHA-256，不训练模型、不写结果。交付副本统一LF换行并用`.gitattributes`固定，避免Windows/Linux转换导致假哈希错误；本地原产物不改写。

共享内容是模型预测/区间、人口及评价汇总，包含原始标记的36条件、30/20/39对的配对比较和逐条件支持。源文件的删列/筛选/换行规范化方式及源SHA见release_provenance.json；数值词法未变。不包含原始CSV、观察逐行预测、26条完整审计快照、配对映射、NPZ或作者原附件。

历史研究报告仍引用本地`results/`、附件或完整语义审计。那些链接在恢复本地材料后才可用，不表示它们已经入库。仓库可用的语义摘要见[Q3_DATA_SEMANTICS_SUMMARY.md](../experiments/reports/Q3_DATA_SEMANTICS_SUMMARY.md)；Q4审核优先使用共享目录，不能依赖旧本地链接。

## 2. 独立Q3环境与测试

实际验证环境为Python 3.12.7。Q1使用的环境不同，不将其版本与Q3混为一套。需要运行科学代码时，在独立环境安装已记录依赖：

```powershell
python -m venv .venv/q3
.venv/q3/Scripts/Activate.ps1
python -m pip install -r requirements-q3.txt
python -B -m unittest discover -s src/python -p 'test_q3*.py' -v
```

完整测试需要将正式Data02放回`data/raw/playbacks/`；其中一个重采样测试会读取它。没有原数据时，可以运行不读原始数据的交付检查、似然检查和Duration合成测试：

```powershell
python -B -m unittest discover -s src/python -p 'test_q3_delivery.py' -v
python -B -m unittest discover -s src/python -p 'test_q3_likelihoods.py' -v
python -B -m unittest discover -s src/python -p 'test_q3_duration_diagnostics.py' -v
```

依赖安装不是本文已执行的动作；版本来自当前实际通过测试的环境，不擅自升级包。

## 3. 重放最终修订：明确恢复冻结上下文

研究脚本保留当时的固定运行ID以追溯证据，本次不为打包重构历史模型。最终四步依赖的24个文件列于`experiments/reports/q3_release/private_context_manifest.json`，其中1项为Data02，其他为冻结模型/OOF/Bootstrap产物。该清单只公布路径、大小和哈希，不公布文件内容。

从P3或团队私有渠道取得这些文件，按清单中的相对路径恢复到项目根；正式Data02可从比赛原附件恢复并核对SHA。不要改时间戳目录名、混用不同运行的元数据，或覆盖已有不匹配文件。检查命令会逐项说明缺失/不匹配：

```powershell
python -B src/python/q3_delivery.py check-context
```

仅克隆仓库时，此命令预期报告缺失并返回2；这是清楚的先决条件检查，不宣称代码可以在缺少历史输入时自动复现所有实验。全24项核对通过、科学依赖已安装后，才执行：

```powershell
python -B src/python/q3_delivery.py run-final
```

它依次调用`q3_final_revision.py`的四步，创建新的`results/q3/final_revision/q3_replay_<UTC>/`，不覆盖历史。可用`--output results/q3/final_revision/<新目录>`指定不存在的目录。它复用既定模型和重复，必要的两个固定C1点门槛仅用于新条件诊断；不是重跑所有历史实验或模型搜索。保存的新运行人口/参数口径与最终方案一致，元数据反映当次真实环境和Git提交。

不需要重放时，直接使用共享的聚合接口即可。旧第一轮/第二轮入口命令见[src/python/README.md](../src/python/README.md)，它们用于研究历史，不作为默认最终入口。

## 4. 交付包如何生成

新增的`q3_package_release.py`只用标准库，从已有、已验收的最终运行做删列和聚合筛选，不拟合模型。命令示例（输出目录必须是新的）：

```powershell
python -B src/python/q3_package_release.py --source results/q3/final_revision/q3_final_20261128T073430Z --output experiments/reports/q3_release_new
```

保留原始产物后再生成新交付目录；脚本拒绝覆盖已存在目录。当前q3_delivery默认检查本次`q3_release`，新版本通过清单审阅后再明确更新入口，不静默替换科学结果。

## 5. 必须随Q4保留的限制

- Latency主人口278行原标记；旧排除V/A的人口只是敏感性，不称已纠错真值。
- Vocal累计量是最终发声增加标记与记录时间≤t的联合概率，不是首次超过基线的时间。
- p_V与计数q不相容的诊断未被校准：36个零基线条件中10个p_V>q，最大6.93pp。联合HVA内部有效不代表跨模块有共同生成分布，不能相乘/相除创造新联合事件。
- Control Approach的条件时间没有直接正记录；真实Duration继续不可识别；旧未来V/A时间预测范围未更新。
- 固定模型逐点置信区间不是未来预测区间或包含模型选择的一切不确定性。

本次上传是已明确这些边界的正式研究版本，不宣称所有生物学语义或科学限制都已解决。
