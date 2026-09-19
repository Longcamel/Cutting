# 上传到 GitHub + 开启 Pages 操作指南

> 完成所有步骤后可删除本文件。

## 第 0 步：替换占位符（重要）

把下面 6 处 `YOUR-NAME` 替换为你的 GitHub 用户名（若仓库名不是 cutting 也一并替换）：

- `README.md`：2 处（git clone 地址、文档站链接）
- `docs/index.html`：4 处（查看源码、下载、bug 反馈、页脚仓库链接）

已本地提交 commit `docs: bilingual README + GitHub Pages site`，
替换后记得再 commit 一次。

## 第 1 步：在 GitHub 创建仓库

1. 打开 https://github.com/new
2. Repository name 填 `cutting`（Public）
3. **不要勾选** "Add a README file"（避免冲突）
4. 点 Create repository

## 第 2 步：推送代码

在项目目录 `D:\Desktop\Cutting` 执行：

```bash
git remote add origin https://github.com/YOUR-NAME/cutting.git
git branch -M main
git push -u origin main
```

（若提示登录，按提示用浏览器授权即可）

## 第 3 步：开启 GitHub Pages

1. 仓库页面 → **Settings** → 左侧 **Pages**
2. Source 选 **Deploy from a branch**
3. Branch 选 **main**，文件夹选 **/docs**，点 Save
4. 等 1~2 分钟，访问：`https://YOUR-NAME.github.io/cutting/`

## 第 4 步（可选）：发布 exe 下载

README 里「下载 Windows 版」链接指向 Releases，发布后才有效：

1. 仓库页面 → 右侧 **Releases** → **Draft a new release**
2. Tag 填 `v1.3.0`，标题 `v1.3.0`
3. 把 `dist\一维下料优化.exe` 拖进附件区
4. 点 Publish release
