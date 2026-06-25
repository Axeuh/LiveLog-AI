# LiveLog-AI - Startup Script
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  LiveLog-AI - Starting..." -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

# 通过 launcher.py 统一启动，所有配置读取 config.yaml。
Write-Host "Starting all services via launcher.py..."
python launcher.py