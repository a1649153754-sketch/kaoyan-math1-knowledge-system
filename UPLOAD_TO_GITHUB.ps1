[CmdletBinding()]
param(
    [string]$RepositoryName = "kaoyan-math1-knowledge-system",
    [ValidateSet("prompt", "public", "private")]
    [string]$Visibility = "prompt"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ExpectedLogin = "a1649153754-sketch"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Description = "可持续迭代的考研数学一知识体系：知识树、公式卡、母题索引、反例库与错题闭环。"
$Topics = @(
    "kaoyan",
    "math-one",
    "mathematics",
    "calculus",
    "linear-algebra",
    "probability",
    "study-notes",
    "zensical"
)

function Write-Step {
    param([string]$Message)
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Read-Confirmation {
    param(
        [string]$Prompt,
        [bool]$DefaultYes = $false
    )

    $suffix = if ($DefaultYes) { "[Y/n]" } else { "[y/N]" }
    while ($true) {
        $answer = (Read-Host "$Prompt $suffix").Trim().ToLowerInvariant()
        if ([string]::IsNullOrWhiteSpace($answer)) {
            return $DefaultYes
        }
        if ($answer -in @("y", "yes", "是")) { return $true }
        if ($answer -in @("n", "no", "否")) { return $false }
        Write-Host "请输入 y 或 n。" -ForegroundColor Yellow
    }
}

function Refresh-ProcessPath {
    $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $parts = @($machinePath, $userPath) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    $env:Path = $parts -join ";"
}

function Find-Executable {
    param(
        [string]$Name,
        [string[]]$FallbackPaths = @()
    )

    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($null -ne $command) {
        return $command.Source
    }

    foreach ($path in $FallbackPaths) {
        if (Test-Path -LiteralPath $path) {
            return $path
        }
    }

    return $null
}

function Install-WithWinget {
    param(
        [string]$PackageId,
        [string]$DisplayName
    )

    $winget = Find-Executable -Name "winget.exe"
    if ($null -eq $winget) {
        throw "未找到 winget，无法自动安装 $DisplayName。请先从 Microsoft Store 安装“应用安装程序”，再重试。"
    }

    if (-not (Read-Confirmation -Prompt "未检测到 $DisplayName，是否通过 winget 安装？" -DefaultYes $true)) {
        throw "缺少 $DisplayName，上传已取消。"
    }

    & $winget install --id $PackageId --exact --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        throw "$DisplayName 安装失败，winget 退出码：$LASTEXITCODE"
    }
    Refresh-ProcessPath
}

function Update-ZensicalRepositoryLinks {
    param(
        [string]$Login,
        [string]$RepoName
    )

    $configPath = Join-Path $ProjectRoot "zensical.toml"
    if (-not (Test-Path -LiteralPath $configPath)) {
        return
    }

    $siteUrl = "https://$Login.github.io/$RepoName/"
    $repoUrl = "https://github.com/$Login/$RepoName"
    $repoNameValue = "$Login/$RepoName"

    $lines = [System.IO.File]::ReadAllLines($configPath)
    $found = @{
        site_url = $false
        repo_url = $false
        repo_name = $false
        edit_uri = $false
    }

    for ($i = 0; $i -lt $lines.Length; $i++) {
        $trimmed = $lines[$i].Trim()
        if ($trimmed -match '^#?\s*site_url\s*=') {
            $lines[$i] = "site_url = `"$siteUrl`""
            $found.site_url = $true
        }
        elseif ($trimmed -match '^#?\s*repo_url\s*=') {
            $lines[$i] = "repo_url = `"$repoUrl`""
            $found.repo_url = $true
        }
        elseif ($trimmed -match '^#?\s*repo_name\s*=') {
            $lines[$i] = "repo_name = `"$repoNameValue`""
            $found.repo_name = $true
        }
        elseif ($trimmed -match '^#?\s*edit_uri\s*=') {
            $lines[$i] = 'edit_uri = "edit/main/docs/"'
            $found.edit_uri = $true
        }
    }

    $missingLines = New-Object System.Collections.Generic.List[string]
    if (-not $found.site_url) { $missingLines.Add("site_url = `"$siteUrl`"") }
    if (-not $found.repo_url) { $missingLines.Add("repo_url = `"$repoUrl`"") }
    if (-not $found.repo_name) { $missingLines.Add("repo_name = `"$repoNameValue`"") }
    if (-not $found.edit_uri) { $missingLines.Add('edit_uri = "edit/main/docs/"') }

    if ($missingLines.Count -gt 0) {
        $projectLine = [Array]::IndexOf($lines, "[project]")
        if ($projectLine -ge 0) {
            $before = @($lines[0..$projectLine])
            $after = if ($projectLine + 1 -lt $lines.Length) { @($lines[($projectLine + 1)..($lines.Length - 1)]) } else { @() }
            $lines = @($before + $missingLines.ToArray() + $after)
        }
    }

    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllLines($configPath, $lines, $utf8NoBom)
}

try {
    Write-Host "考研数学一知识体系 · GitHub 一键上传" -ForegroundColor Green
    Write-Host "项目目录：$ProjectRoot"
    Write-Host "脚本不会读取或保存你的 GitHub 密码、令牌。登录由 GitHub CLI 官方网页授权完成。" -ForegroundColor DarkGray

    Write-Step "检查 Git"
    $git = Find-Executable -Name "git.exe" -FallbackPaths @(
        "$env:ProgramFiles\Git\cmd\git.exe",
        "$env:LOCALAPPDATA\Programs\Git\cmd\git.exe"
    )
    if ($null -eq $git) {
        Install-WithWinget -PackageId "Git.Git" -DisplayName "Git"
        $git = Find-Executable -Name "git.exe" -FallbackPaths @(
            "$env:ProgramFiles\Git\cmd\git.exe",
            "$env:LOCALAPPDATA\Programs\Git\cmd\git.exe"
        )
    }
    if ($null -eq $git) { throw "Git 安装后仍未找到，请重新打开脚本。" }
    Write-Host (& $git --version)

    Write-Step "检查 GitHub CLI"
    $gh = Find-Executable -Name "gh.exe" -FallbackPaths @(
        "$env:ProgramFiles\GitHub CLI\gh.exe",
        "$env:LOCALAPPDATA\Programs\GitHub CLI\gh.exe"
    )
    if ($null -eq $gh) {
        Install-WithWinget -PackageId "GitHub.cli" -DisplayName "GitHub CLI"
        $gh = Find-Executable -Name "gh.exe" -FallbackPaths @(
            "$env:ProgramFiles\GitHub CLI\gh.exe",
            "$env:LOCALAPPDATA\Programs\GitHub CLI\gh.exe"
        )
    }
    if ($null -eq $gh) { throw "GitHub CLI 安装后仍未找到，请重新打开脚本。" }
    Write-Host (& $gh --version | Select-Object -First 1)

    Write-Step "登录 GitHub"
    & $gh auth status --hostname github.com *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "浏览器将打开 GitHub 官方授权页面。完成登录后回到本窗口。" -ForegroundColor Yellow
        & $gh auth login --hostname github.com --git-protocol https --web
        if ($LASTEXITCODE -ne 0) { throw "GitHub 登录未完成。" }
    }
    & $gh auth setup-git
    if ($LASTEXITCODE -ne 0) { throw "Git 凭据配置失败。" }

    $login = ((& $gh api user --jq '.login') | Out-String).Trim()
    $userId = ((& $gh api user --jq '.id') | Out-String).Trim()
    if ([string]::IsNullOrWhiteSpace($login)) { throw "无法读取当前 GitHub 用户名。" }

    Write-Host "当前登录账号：$login" -ForegroundColor Green
    if ($login -ne $ExpectedLogin) {
        Write-Host "注意：当前账号与 ChatGPT 中连接的账号 $ExpectedLogin 不同。" -ForegroundColor Yellow
        if (-not (Read-Confirmation -Prompt "仍然上传到 $login 吗？" -DefaultYes $false)) {
            throw "已取消，未上传任何内容。"
        }
    }

    if ($Visibility -eq "prompt") {
        while ($true) {
            Write-Host "`n请选择仓库可见性："
            Write-Host "  1. public  —— 公开，任何人都能查看，适合开源与 GitHub Pages"
            Write-Host "  2. private —— 私有，只有你和获授权的人能查看"
            $choice = (Read-Host "输入 1 或 2").Trim()
            if ($choice -eq "1") { $Visibility = "public"; break }
            if ($choice -eq "2") { $Visibility = "private"; break }
            Write-Host "请输入 1 或 2。" -ForegroundColor Yellow
        }
    }

    $fullRepository = "$login/$RepositoryName"
    $repositoryUrl = "https://github.com/$fullRepository"

    Write-Host "`n即将执行：" -ForegroundColor Cyan
    Write-Host "  仓库：$fullRepository"
    Write-Host "  可见性：$Visibility"
    Write-Host "  来源：$ProjectRoot"
    if ($Visibility -eq "public") {
        Write-Host "  注意：公开仓库中的全部文件将对互联网可见。" -ForegroundColor Yellow
    }
    if (-not (Read-Confirmation -Prompt "确认创建或更新该仓库并推送全部项目文件？" -DefaultYes $false)) {
        throw "已取消，未上传任何内容。"
    }

    Write-Step "写入项目仓库链接"
    Update-ZensicalRepositoryLinks -Login $login -RepoName $RepositoryName

    Write-Step "初始化本地 Git 仓库"
    Set-Location -LiteralPath $ProjectRoot
    & $git rev-parse --is-inside-work-tree *> $null
    if ($LASTEXITCODE -ne 0) {
        & $git init
        if ($LASTEXITCODE -ne 0) { throw "git init 失败。" }
    }
    & $git branch -M main
    if ($LASTEXITCODE -ne 0) { throw "无法设置 main 分支。" }

    & $git config user.name $login
    if (-not [string]::IsNullOrWhiteSpace($userId)) {
        & $git config user.email "$userId+$login@users.noreply.github.com"
    }

    & $git add --all
    if ($LASTEXITCODE -ne 0) { throw "git add 失败。" }

    & $git diff --cached --quiet
    $hasStagedChanges = ($LASTEXITCODE -ne 0)
    & $git rev-parse --verify HEAD *> $null
    $hasCommit = ($LASTEXITCODE -eq 0)

    if ($hasStagedChanges -or -not $hasCommit) {
        & $git commit -m "chore: publish kaoyan math1 knowledge system v1.2"
        if ($LASTEXITCODE -ne 0) { throw "git commit 失败。" }
    }
    else {
        Write-Host "没有新的本地变更，跳过提交。"
    }

    Write-Step "创建或连接 GitHub 仓库"
    & $gh repo view $fullRepository --json nameWithOwner *> $null
    $repositoryExists = ($LASTEXITCODE -eq 0)

    if ($repositoryExists) {
        Write-Host "GitHub 上已存在 $fullRepository。" -ForegroundColor Yellow
        if (-not (Read-Confirmation -Prompt "使用现有仓库并推送 main 分支？" -DefaultYes $false)) {
            throw "已取消，未推送到现有仓库。"
        }

        $expectedRemote = "$repositoryUrl.git"
        $origin = ((& $git remote get-url origin 2>$null) | Out-String).Trim()
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($origin)) {
            & $git remote add origin $expectedRemote
            if ($LASTEXITCODE -ne 0) { throw "添加 origin 失败。" }
        }
        elseif ($origin -ne $expectedRemote -and $origin -ne "git@github.com:$fullRepository.git") {
            Write-Host "当前 origin：$origin" -ForegroundColor Yellow
            Write-Host "目标 origin：$expectedRemote" -ForegroundColor Yellow
            if (-not (Read-Confirmation -Prompt "是否把 origin 改为目标仓库？" -DefaultYes $false)) {
                throw "为避免推送到错误仓库，操作已取消。"
            }
            & $git remote set-url origin $expectedRemote
            if ($LASTEXITCODE -ne 0) { throw "修改 origin 失败。" }
        }

        & $git push --set-upstream origin main
        if ($LASTEXITCODE -ne 0) {
            throw "推送失败。若现有仓库不是空仓库，请先处理远端已有提交，再重新运行。"
        }
    }
    else {
        $createArgs = @(
            "repo", "create", $fullRepository,
            "--source", $ProjectRoot,
            "--remote", "origin",
            "--push",
            "--description", $Description,
            "--$Visibility"
        )
        & $gh @createArgs
        if ($LASTEXITCODE -ne 0) { throw "GitHub 仓库创建或首次推送失败。" }
    }

    Write-Step "补充仓库信息"
    $editArgs = @("repo", "edit", $fullRepository, "--homepage", "https://$login.github.io/$RepositoryName/")
    foreach ($topic in $Topics) {
        $editArgs += @("--add-topic", $topic)
    }
    & $gh @editArgs
    if ($LASTEXITCODE -ne 0) {
        Write-Host "项目已上传，但仓库 Topics 或主页地址未能自动设置，可稍后在网页中修改。" -ForegroundColor Yellow
    }

    Write-Host "`n上传完成！" -ForegroundColor Green
    Write-Host "仓库地址：$repositoryUrl" -ForegroundColor Green
    Write-Host "`n要启用文档站：进入仓库 Settings → Pages，将 Source 设为 GitHub Actions。"
    Write-Host "然后到 Actions 查看 Deploy documentation 工作流。"
    Write-Host "预计站点地址：https://$login.github.io/$RepositoryName/"
    exit 0
}
catch {
    Write-Host "`n上传未完成：$($_.Exception.Message)" -ForegroundColor Red
    Write-Host "项目文件没有丢失，可以修正问题后重新运行本脚本。" -ForegroundColor Yellow
    exit 1
}
