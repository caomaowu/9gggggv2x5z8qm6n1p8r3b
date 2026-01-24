$ErrorActionPreference = "Stop"

$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $SCRIPT_DIR

Write-Host "================================" -ForegroundColor Cyan
Write-Host "停止后台回测守护进程" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

$TOOLS_DIR = Split-Path $SCRIPT_DIR -Parent
$DATA_DIR = Join-Path $TOOLS_DIR "data"
$STATUS_FILE = Join-Path $DATA_DIR "batch_backtest_status.json"

if (-not (Test-Path $STATUS_FILE)) {
    Write-Host "守护进程状态文件不存在，可能未启动过" -ForegroundColor Yellow
    pause
    exit 0
}

try {
    $STATUS = Get-Content $STATUS_FILE -Raw | ConvertFrom-Json
    $PID = $STATUS.pid

    if (-not $PID) {
        Write-Host "状态文件中未找到进程 ID" -ForegroundColor Yellow
        pause
        exit 0
    }

    $PROCESS = Get-Process -Id $PID -ErrorAction SilentlyContinue

    if (-not $PROCESS) {
        Write-Host "进程 $PID 不存在，可能已经停止" -ForegroundColor Yellow
        Remove-Item $STATUS_FILE -Force
        Write-Host "已清理状态文件" -ForegroundColor Green
        pause
        exit 0
    }

    Write-Host "找到守护进程 (PID: $PID)" -ForegroundColor Green
    Write-Host ""

    $CONFIRM = Read-Host "确认停止此进程？(y/N)"
    if ($CONFIRM -ne "y" -and $CONFIRM -ne "Y") {
        Write-Host "已取消操作" -ForegroundColor Yellow
        pause
        exit 0
    }

    Stop-Process -Id $PID -Force

    Start-Sleep -Seconds 1

    $PROCESS = Get-Process -Id $PID -ErrorAction SilentlyContinue
    if ($PROCESS) {
        Write-Host "警告: 进程可能未正常停止，尝试强制终止..." -ForegroundColor Yellow
        Stop-Process -Id $PID -Force -ErrorAction SilentlyContinue
    }

    Remove-Item $STATUS_FILE -Force
    Write-Host "守护进程已停止" -ForegroundColor Green
    Write-Host "状态文件已清理" -ForegroundColor Green

} catch {
    Write-Host "停止失败: $_" -ForegroundColor Red
    pause
    exit 1
}

Write-Host ""
Write-Host "按任意键退出..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
