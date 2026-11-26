# GitHub 协作步骤

## 仓库设置

仓库名：apmcm-2026-c；可见性：Private；默认分支：main。

第一次在 GitHub 创建时不要初始化 README、.gitignore 或 License，本地已准备文件和提交，避免出现两套独立历史。

## 克隆后准备

1. 从正式比赛附件恢复 problem/、data/raw/、src/reference_R/ 中的本地材料。
2. 依 data/README.md 核对文件结构；不要覆盖或清洗原始数据。
3. 在 src/ 中开发代码，记录实际依赖后再创建依赖清单。
4. 在 paper/latex/main.tex 填写队号。控制页、签名和个人资料仅本地保存。

## 日常操作

在 MathModeling 目录中运行：

```powershell
git status
git pull --ff-only
git switch -c feature/your-task
# 修改代码或论文后，先检查差异
git diff
git add <具体文件路径>
git diff --cached
git commit -m "Describe the change"
git push -u origin feature/your-task
```

通过 GitHub 的 Pull Request 合并代码。独自使用 main 分支时，也应先 pull、检查改动再 commit 和 push。

.gitignore 不会移除已经跟踪的文件。不要用 git add -f 绕过忽略规则上传原始数据、签名文件或凭据。推送前用 git diff --cached --name-only 查看实际文件清单。

## 本次执行进度

- 本地框架准备和提交由本会话执行，结果见 Git 历史。
- 远端创建与推送状态以实际 GitHub 仓库和本地 remote 为准；本文不预先声明已完成。
