<#
.SYNOPSIS
    AutoNewsAnalyzer 一键部署（Windows，幂等）

.DESCRIPTION
    依次完成：环境检查 → 创建虚拟环境 → 安装依赖 → 生成 .env → 跑测试 → 冒烟运行。
    可选 -Start 以常驻方式启动并验证 /metrics 端点。

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\deploy.ps1

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\deploy.ps1 -Start -MetricsPort 9090

.NOTES
    真实 API Key 只会写入 .env（已被 .gitignore 忽略），脚本不会把它写进任何源码。
#>
param(
    [switch]$Full,          # 安装完整依赖（含 spacy/torch 等，体积大）
    [switch]$SkipTests,     # 跳过 pytest
    [switch]$WithLlm,       # 冒烟测试时启用大模型（会产生 API 费用）
    [switch]$Start,         # 部署完成后常驻启动
    [int]$Cycles = 1,
    [int]$MetricsPort = 9090
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Step($name) { Write-Host "`n=== $name ===" -ForegroundColor Cyan }
function Ok($msg)    { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Warn($msg)  { Write-Host "  [!]  $msg" -ForegroundColor Yellow }
function Fail($msg)  { Write-Host "  [X]  $msg" -ForegroundColor Red; exit 1 }

Write-Host "AutoNewsAnalyzer 部署脚本" -ForegroundColor White
Write-Host "项目目录: $Root"

# ---------------------------------------------------------------- 0. 环境检查
Step "0. 环境检查"
$python = $null
foreach ($candidate in @('python', 'py')) {
    $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
    if ($cmd) { $python = $candidate; break }
}
if (-not $python) { Fail "未找到 Python，请先安装 Python 3.10+" }

$versionOk = & $python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
if ($LASTEXITCODE -ne 0) { Fail "Python 版本过低，需要 3.10+（当前: $(& $python --version)）" }
Ok "Python: $(& $python --version)"

$venvDir = Join-Path $Root '.venv'
$venvPy = Join-Path $venvDir 'Scripts\python.exe'

# ---------------------------------------------------------------- 1. 虚拟环境
Step "1. 虚拟环境"
if (Test-Path $venvPy) {
    Ok "已存在: .venv"
} else {
    & $python -m venv $venvDir
    if ($LASTEXITCODE -ne 0) { Fail "创建虚拟环境失败" }
    Ok "已创建: .venv"
}
& $venvPy -m pip install --disable-pip-version-check -q --upgrade pip 2>&1 | Out-Null

# ---------------------------------------------------------------- 2. 依赖
Step "2. 安装依赖"
$req = if ($Full) { 'requirements.txt' } else { 'requirements-core.txt' }
Write-Host "  使用: $req"
& $venvPy -m pip install --disable-pip-version-check -q -r $req
if ($LASTEXITCODE -ne 0) { Fail "依赖安装失败（检查网络或改用 -Full）" }
Ok "依赖安装完成"

# ---------------------------------------------------------------- 3. 配置
Step "3. 环境变量"
$envFile = Join-Path $Root '.env'
if (Test-Path $envFile) {
    Ok ".env 已存在，保持不动（不覆盖已有密钥）"
} else {
    Copy-Item (Join-Path $Root '.env.example') $envFile
    Ok "已从 .env.example 生成 .env（DEEPSEEK_API_KEY 为空 = 规则提取模式）"
}
$keyInEnv = $env:DEEPSEEK_API_KEY
$keyInFile = Select-String -Path $envFile -Pattern '^\s*DEEPSEEK_API_KEY\s*=\s*\S+' -Quiet
if ($keyInEnv) { Ok "检测到环境变量 DEEPSEEK_API_KEY（优先于 .env）" }
elseif ($keyInFile) { Ok ".env 中已配置 DEEPSEEK_API_KEY" }
else { Warn "未配置大模型密钥，将以规则提取模式运行（不影响主流程）" }

# ---------------------------------------------------------------- 4. 测试
if (-not $SkipTests) {
    Step "4. 运行测试"
    & $venvPy -m pytest tests/ -q
    if ($LASTEXITCODE -ne 0) { Fail "测试未通过，部署中止" }
    Ok "测试全部通过"
} else {
    Step "4. 运行测试（已跳过）"
}

# ---------------------------------------------------------------- 5. 冒烟
Step "5. 冒烟运行"
$smokeArgs = @('main.py', '--cycles', "$Cycles")
if (-not $WithLlm) { $smokeArgs += '--no-llm' }
& $venvPy @smokeArgs
if ($LASTEXITCODE -ne 0) { Fail "冒烟运行失败（见上方输出）" }

$reportDir = Join-Path $Root 'output'
$latestReport = Get-ChildItem $reportDir -Filter '*.json' -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime | Select-Object -Last 1
if (-not $latestReport) { Fail "未生成运行报告" }
Ok "报告已生成: output\$($latestReport.Name)"

# ---------------------------------------------------------------- 6. 常驻启动
if ($Start) {
    Step "6. 常驻启动"
    $logDir = Join-Path $Root 'data\logs'
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null
    $outLog = Join-Path $logDir 'run.out.log'
    $errLog = Join-Path $logDir 'run.err.log'
    $proc = Start-Process -FilePath $venvPy `
        -ArgumentList @('main.py', '--continuous', '--interval', '3600', '--metrics-port', "$MetricsPort") `
        -WorkingDirectory $Root `
        -RedirectStandardOutput $outLog `
        -RedirectStandardError $errLog `
        -PassThru
    $proc.Id | Set-Content (Join-Path $Root 'data\run.pid')
    Ok "已启动 (PID $($proc.Id))，日志: data\logs\run.out.log"

    $ready = $false
    for ($i = 0; $i -lt 20; $i++) {
        Start-Sleep -Milliseconds 500
        try {
            $resp = Invoke-WebRequest -Uri "http://127.0.0.1:$MetricsPort/metrics" -UseBasicParsing -TimeoutSec 2
            if ($resp.StatusCode -eq 200 -and $resp.Content -match 'autonews_') {
                $ready = $true
                break
            }
        } catch { }
    }
    if ($ready) { Ok "指标端点正常: http://127.0.0.1:$MetricsPort/metrics" }
    else { Warn "指标端点暂未就绪，可稍后重试（进程仍在运行）" }
}

# ---------------------------------------------------------------- 7. 汇总
Step "完成"
Write-Host "  启动:     .\.venv\Scripts\python.exe main.py --cycles 3"
Write-Host "  常驻:     .\.venv\Scripts\python.exe main.py --continuous --interval 3600 --metrics-port 9090"
Write-Host "  查看评估: .\.venv\Scripts\python.exe main.py --evaluate"
Write-Host "  停止常驻: Stop-Process -Id (Get-Content data\run.pid)"
Write-Host ""
Write-Host "  部署成功。" -ForegroundColor Green
