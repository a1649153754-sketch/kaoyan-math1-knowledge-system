# 上传到 GitHub

本项目默认仓库名：

```text
kaoyan-math1-knowledge-system
```

当前为 GitHub 账号 `a1649153754-sketch` 做了上传预配置。脚本会以实际登录账号为准；若账号不同，会在推送前再次确认。

## 方法 A：Windows 一键上传（推荐）

1. 解压项目 ZIP。
2. 双击项目根目录中的 `UPLOAD_TO_GITHUB.cmd`。
3. 脚本会检查 Git 和 GitHub CLI；缺失时会先征得同意，再通过 `winget` 安装。
4. 首次使用时，浏览器会打开 GitHub 官方授权页。登录并授权后回到命令窗口。
5. 明确选择仓库为 `public` 或 `private`，核对目标仓库，再确认推送。

脚本会自动完成：

- 创建本地 Git 仓库并提交全部文件；
- 使用 GitHub 的 `noreply` 邮箱作为本仓库提交邮箱，避免公开个人邮箱；
- 创建或连接 GitHub 仓库；
- 推送 `main` 分支；
- 写入 `zensical.toml` 中的仓库与文档站链接；
- 添加项目简介、主页地址和 Topics。

脚本不会读取、保存或要求你粘贴 GitHub 密码、Personal Access Token。

> 公开仓库会让所有项目文件对互联网可见。脚本不会替你默认选择，必须由你明确输入 `1` 或 `2`。

## 方法 B：手动使用 Git 命令

先在 GitHub 新建一个**空仓库**。不要勾选自动创建 README、License 或 `.gitignore`，然后在本项目根目录运行：

```bash
git init
git add .
git commit -m "chore: initialize kaoyan math1 knowledge system"
git branch -M main
git remote add origin https://github.com/a1649153754-sketch/kaoyan-math1-knowledge-system.git
git push -u origin main
```

第一次推送时，Git 会要求通过浏览器或系统凭据管理器登录 GitHub。不要把密码或令牌发给其他人。

## 方法 C：网页上传

1. 在 GitHub 新建空仓库。
2. 解压项目 ZIP。
3. 在仓库页面选择上传文件，把解压后的**文件夹内部内容**全部拖入。
4. 提交说明填写 `chore: initialize project`。

使用网页上传时，要确认 `.github/` 文件夹也被保留，否则自动部署工作流不会上传。

## 开启 GitHub Pages

上传完成后：

1. 进入仓库 `Settings`。
2. 打开 `Pages`。
3. 在 `Build and deployment` 的 `Source` 中选择 **GitHub Actions**。
4. 回到 `Actions` 页面，查看 `Deploy documentation` 工作流。

预计文档站地址：

```text
https://a1649153754-sketch.github.io/kaoyan-math1-knowledge-system/
```

## 推荐仓库信息

**Description：**

```text
可持续迭代的考研数学一知识体系：知识树、公式卡、母题索引、反例库与错题闭环。
```

**Topics：**

```text
kaoyan, math-one, mathematics, calculus, linear-algebra, probability, study-notes, zensical
```

`social-preview.png` 已放在项目根目录，可在仓库设置中作为 Social preview 上传。
