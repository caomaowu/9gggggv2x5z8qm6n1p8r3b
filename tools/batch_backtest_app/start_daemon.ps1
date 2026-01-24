$ErrorActionPreference = "Stop"

$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $SCRIPT_DIR

Write-Host "================================" -ForegroundColor Cyan
Write-Host "后台回测守护进程启动脚本" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

$PYTHON_CMD = Get-Command python -ErrorAction SilentlyContinue
if (-not $PYTHON_CMD) {
    $PYTHON_CMD = Get-Command python3 -ErrorAction SilentlyContinue
}

if (-not $PYTHON_CMD) {
    Write-Host "错误: 未找到 Python，请先安装 Python" -ForegroundColor Red
    Write-Host "请访问 https://www.python.org/downloads/ 下载安装" -ForegroundColor Yellow
    pause
    exit 1
}

$PYTHON_VERSION = & python --version 2>&1
Write-Host "检测到 Python: $PYTHON_VERSION" -ForegroundColor Green

$DAEMON_SCRIPT = Join-Path $SCRIPT_DIR "batch_backtest_daemon.py"
$TOOLS_DIR = Split-Path $SCRIPT_DIR -Parent
$DATA_DIR = Join-Path $TOOLS_DIR "data"

if (-not (Test-Path $DAEMON_SCRIPT)) {
    Write-Host "错误: 未找到守护进程脚本 $DAEMON_SCRIPT" -ForegroundColor Red
    pause
    exit 1
}

Write-Host "正在启动守护进程..." -ForegroundColor Yellow
Write-Host "脚本路径: $DAEMON_SCRIPT" -ForegroundColor DarkGray
Write-Host ""

try {
    Start-Process -FilePath python -ArgumentList $DAEMON_SCRIPT -NoNewWindow -RedirectStandardOutput "$DATA_DIR\daemon_stdout.log" -RedirectStandardError "$DATA_DIR\daemon_stderr.log"

    Start-Sleep -Seconds 2

    Write-Host "守护进程已启动！" -ForegroundColor Green
    Write-Host ""
    Write-Host "日志文件位置:" -ForegroundColor Cyan
    Write-Host "  - 主日志: $DATA_DIR\daemon.log" -ForegroundColor DarkGray
    Write-Host "  - 标准输出: $DATA_DIR\daemon_stdout.log" -ForegroundColor DarkGray
    Write-Host "  - 错误输出: $DATA_DIR\daemon_stderr.log" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "使用 Ctrl+C 或关闭此窗口不会影响守护进程运行" -ForegroundColor Yellow
    Write-Host "如需停止守护进程，请在 Web UI 的 '🔧 后台任务管理' 页面点击停止按钮" -ForegroundColor Yellow
    Write-Host ""

} catch {
    Write-Host "启动失败: $_" -ForegroundColor Red
    pause
    exit 1
}

Write-Host "按任意键退出此启动窗口（守护进程将继续在后台运行）..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
