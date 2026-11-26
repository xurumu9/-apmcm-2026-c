# GitHub 协作步骤

## 仓库设置

实际仓库：[xurumu9/-apmcm-2026-c](https://github.com/xurumu9/-apmcm-2026-c)，名称开头有连字符。可见性 Private（2026-11-26 首次推送时核实），默认分支 main。初始提交 7332fff 已推送并核对远端。

保持私有，变更需队内明确决定。通过 Settings → Collaborators 邀请成员真实账号，P1/P2/P3 只是代号。以下为团队约定，尚未配置 GitHub 分支保护、强制审核或 CI，不得宣称平台已强制执行。

## 分支与审阅

main 保存经审阅的集成版本。日常使用短期任务分支和 PR，不直接推送 main。

| 工作 | 分支示例 | 主责 | 审阅 |
|---|---|---|---|
| 数据/Q1 | p1/data-audit、p1/q1-baseline | P1 | P2 |
| Q2/Q4 | p2/q2-propagation、p2/q4-scenarios | P2 | P3 |
| Q3/论文 | p3/q3-response、p3/paper-integration | P3 | P1 |
| 共享文档 | docs/project-framework | 当前负责人 | 非作者成员 |

至少一名非作者真实审核；跨模块接口与综合主结论三人共同确认，不虚构批准。代号用于分支，不伪造 Git 作者。

## 克隆后准备

1. 从正式比赛附件恢复 problem/、data/raw/、src/reference_R/ 中的本地材料。
2. 依 data/README.md 核对文件结构；不要覆盖或清洗原始数据。
3. 在 src/ 中开发代码，记录实际依赖后再创建依赖清单。
4. 在 paper/latex/main.tex 填写队号。控制页、签名和个人资料仅本地保存。

## 日常操作

在 MathModeling 目录中运行：

```powershell
git status
git switch main
git pull --ff-only
git switch -c p1/data-audit
# 修改代码或论文后，先检查差异
git diff
git add <具体文件路径>
git diff --cached
git commit -m "Describe the change"
git push -u origin p1/data-audit
```

示例分支按实际任务替换；切换前存在未提交改动时先保存并确认处理，不 reset 或覆盖文件。

在 GitHub 创建 PR：base=main，compare=任务分支。说明问题与改动、数据/接口/假设影响、实际验证、实验 ID、结果摘要、限制、关联决策和 AI 记录。合并前核对 main 更新、人工处理冲突、必要检查及文件清单；建议 Squash and merge。禁止 force-push 共享 main。合并后切回 main 并 git pull --ff-only。

.gitignore 不会移除已经跟踪的文件。不要用 git add -f 绕过忽略规则上传原始数据、签名文件或凭据。推送前用 git diff --cached --name-only 查看实际文件清单。

## 共享产物

追踪代码、研究文档、论文源文件、必要小型图表、实验记录与精简汇总。原始附件、逐条派生数据、results、控制页、PDF/Word、音视频与编译产物保持本地。

供审核的精简汇总及运行元数据放 experiments/reports/，不复制原始逐条记录和个人资料。完整产物通过队内私有渠道传递，核对运行 ID/哈希。仓库不替代赛事提交。

研究分工见 [TEAM_ROLES.md](docs/TEAM_ROLES.md)。
