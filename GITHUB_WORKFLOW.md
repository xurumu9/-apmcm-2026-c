# GitHub 协作步骤

## 仓库设置

实际仓库：[xurumu9/-apmcm-2026-c](https://github.com/xurumu9/-apmcm-2026-c)，名称开头有连字符。2026-11-26 曾记录为 Private；2026-11-27 查询 GitHub 仓库元数据时为 Public。默认分支 main。此次核对未改变仓库可见性。

2026-11-28通过GitHub API核实仓库现为Public；用户明确确认保持公开并上传P3分支。上段Private为首次推送时的历史记录，当前以Public为准。通过 Settings → Collaborators 邀请成员真实账号，P1/P2/P3 只是代号。以下为团队约定，尚未配置 GitHub 分支保护、强制审核或 CI，不得宣称平台已强制执行。

## 日常协作

团队任务和截止日期只见 [TEAM_PLAN.md](docs/TEAM_PLAN.md)。按任务使用短期分支，需要讨论合并时使用 PR；不设置固定审核角色。分支名可用 p1/data-audit 等易懂名称。

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

P2 于 2026-11-27 明确要求上传已生成成果：`member2-propagation` 分支为该成员的传播长表和六份 Q2 结果增加逐个例外，详见 `results/q2/README.md`。该长表包含原始相关值；当前仓库公开。此例外不扩展到其他成员数据，也不允许上传原始附件或凭据。其余分支是否接纳此例外由队伍决定。

供审核的精简汇总及运行元数据放 experiments/reports/，不复制原始逐条记录和个人资料。完整产物通过队内私有渠道传递，核对运行 ID/哈希。仓库不替代赛事提交。

数据接口见 [TEAM_ROLES.md](docs/TEAM_ROLES.md)。
