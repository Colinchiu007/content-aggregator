$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

$workspace = "C:\Users\邱领\.qclaw\workspace\content-aggregator"
$logFile = "$workspace\server.log"

Write-Host "🚀 正在启动 Content Aggregator 服务器..." -ForegroundColor Cyan
Write-Host "📝 日志文件: $logFile" -ForegroundColor Yellow

Set-Location $workspace

# 启动服务器，重定向输出到日志文件
Start-Process -FilePath "python" `
    -ArgumentList "web/server.py" `
    -WorkingDirectory $workspace `
    -RedirectStandardOutput $logFile `
    -RedirectStandardError $logFile `
    -WindowStyle Hidden

# 等待服务器启动
Start-Sleep -Seconds 5

# 检查端口
$portOpen = Test-NetConnection -ComputerName "localhost" -Port 8000 -InformationLevel Quiet -ErrorAction SilentlyContinue
if ($portOpen) {
    Write-Host "✅ 服务器启动成功！端口 8000 已监听" -ForegroundColor Green
    Write-Host "🌐 访问地址: http://localhost:8000" -ForegroundColor Cyan
} else {
    Write-Host "❌ 服务器启动失败，请查看日志:" -ForegroundColor Red
    Write-Host $logFile -ForegroundColor Yellow
    if (Test-Path $logFile) {
        Get-Content $logFile -Tail 20 | Write-Host
    }
}
