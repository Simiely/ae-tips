param(
    [Parameter(Mandatory = $true)][string]$Jsx,
    [string]$Log = "",
    [int]$TimeoutSec = 300,
    [string]$AePath = "C:\Program Files\Adobe\Adobe After Effects 2026\Support Files\AfterFX.exe",
    [switch]$KeepRunning
)

# 无头运行 AE ExtendScript。
# 时序是硬要求:等主窗口标题非空 -> 再 sleep 1.5s -> 才 -r,否则脚本静默不执行。
# 退出判据:jsx 末尾必须 app.quit();本脚本等 AfterFX 进程消失才认为脚本结束。
# 日志:jsx 里 L() 逐行 open/append/close;File 在 close() 才落盘,所以崩溃也能看到最后一行。

$ErrorActionPreference = "Stop"

if (-not (Test-Path $AePath)) { throw "找不到 AE: $AePath(用 -AePath 指定)" }
$Jsx = (Resolve-Path $Jsx).Path
if ($Log -eq "") {
    $Log = [System.IO.Path]::ChangeExtension($Jsx, ".log.txt")
}
$Log = [System.IO.Path]::GetFullPath($Log)
if (Test-Path $Log) { Remove-Item $Log -Force }

Write-Host "[run_ae] AE      = $AePath"
Write-Host "[run_ae] JSX     = $Jsx"
Write-Host "[run_ae] LOG     = $Log"

$existing = Get-Process AfterFX -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "[run_ae] 关闭已存在的 AfterFX($($existing.Count) 个)—— 无头运行不能接管已有实例"
    $existing | Stop-Process -Force
    Start-Sleep -Milliseconds 800
}

Write-Host "[run_ae] 启动 AE ..."
Start-Process -FilePath $AePath

# ---- 阶段 1:等主窗口就绪 -------------------------------------------------
$deadline = (Get-Date).AddSeconds(90)
while ((Get-Date) -lt $deadline) {
    $p = Get-Process AfterFX -ErrorAction SilentlyContinue |
        Where-Object { $_.MainWindowTitle -ne "" } | Select-Object -First 1
    if ($p) { break }
    Start-Sleep -Milliseconds 500
}
if (-not $p) { throw "[run_ae] 90s 内 AE 主窗口没有就绪,放弃(此时 -r 会静默丢脚本)" }
Write-Host "[run_ae] 主窗口就绪: $($p.MainWindowTitle)"
Start-Sleep -Milliseconds 1500

# ---- 阶段 2:投递脚本 ------------------------------------------------------
# ★ 不要用 `& $AePath -r $Jsx`:在嵌套 PowerShell(`powershell -File`)里,等 AE 退出后
#   会抛 `You cannot call a method on a null-valued expression` —— **脚本其实已经跑完**,
#   只是包装层报错、退出码变成 1。改用 Start-Process(不等),退出由阶段 3 轮询。
Write-Host "[run_ae] afterfx -r <jsx> ..."
Start-Process -FilePath $AePath -ArgumentList @("-r", $Jsx) | Out-Null

# ---- 阶段 3:等脚本结束 ----------------------------------------------------
# jsx 末尾 app.quit() => 进程退出即脚本结束。
# 不设这条,只能靠日志猜,而日志正好是最不可靠的那一环。
Write-Host "[run_ae] 等 AfterFX 退出(上限 ${TimeoutSec}s)..."
# Start-Process 立即返回 ⇒ 先等进程真的出现,否则第一轮轮询会误判"已退出"
$spawn = (Get-Date).AddSeconds(10)
while ((Get-Date) -lt $spawn) {
    if (Get-Process AfterFX -ErrorAction SilentlyContinue) { break }
    Start-Sleep -Milliseconds 300
}
$sw = [Diagnostics.Stopwatch]::StartNew()
while ($sw.Elapsed.TotalSeconds -lt $TimeoutSec) {
    $p2 = Get-Process AfterFX -ErrorAction SilentlyContinue
    if (-not $p2) { break }
    Start-Sleep -Milliseconds 500
}
$sw.Stop()

$still = Get-Process AfterFX -ErrorAction SilentlyContinue
if ($still -and -not $KeepRunning) {
    Write-Host "[run_ae] 超时 $TimeoutSec s 仍未退出,强制结束进程(日志可能是半截)"
    $still | Stop-Process -Force
}
Write-Host ("[run_ae] 结束,耗时 {0:N1}s" -f $sw.Elapsed.TotalSeconds)

# ---- 阶段 4:回读日志 ------------------------------------------------------
if (-not (Test-Path $Log)) {
    Write-Host "[run_ae] !! 日志不存在:脚本很可能根本没被执行(先查冷启动时序)"
    exit 2
}
$lines = Get-Content $Log -Encoding UTF8
Write-Host "[run_ae] 日志 $($lines.Count) 行:"
$lines | ForEach-Object { Write-Host "  $_" }

# ★ 日志每行前面带时间戳("Thu Oct 29 2026 17:22:21 GMT+0800  DONE"),
#   用 ^DONE 永远匹配不到 —— 实测三次构建全部被误判成"中途崩"。必须匹配行尾。
if ($lines -match "DONE$") { exit 0 }
Write-Host "[run_ae] !! 日志里没有 DONE:脚本中途崩/被中断(最后一行就是崩溃点)"
exit 1
