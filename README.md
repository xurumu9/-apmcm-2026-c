# 2026 APMCM Problem C

非洲企鹅海上声学通信与回放响应建模项目。

## 目录

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

