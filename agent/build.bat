@echo off
chcp 65001 > nul
title axeuh-agent 构建脚本

echo ========================================
echo   axeuh-agent 构建脚本
echo ========================================
echo.

:: 检查 pyinstaller
where pyinstaller >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [错误] 未找到 pyinstaller，请先安装:
    echo   pip install pyinstaller
    pause
    exit /b 1
)

:: 检查入口文件
if not exist agent_server.py (
    echo [错误] 未找到 agent_server.py
    echo 请在 agent/ 目录下运行此脚本
    pause
    exit /b 1
)

echo [1/3] 清理旧构建...
if exist build rmdir /s /q build >nul 2>&1
if exist dist rmdir /s /q dist >nul 2>&1
if exist axeuh-agent.spec del axeuh-agent.spec >nul 2>&1

echo [2/3] 开始打包...
pyinstaller --onefile --name axeuh-agent ^
    --add-data "config.json;." ^
    --hidden-import websockets ^
    --noconsole ^
    agent_server.py

if %ERRORLEVEL% NEQ 0 (
    echo [错误] 打包失败
    pause
    exit /b 1
)

echo [3/3] 打包完成!
echo.
echo 输出文件: %cd%\dist\axeuh-agent.exe
echo.
echo 使用方式:
echo   1. 将 axeuh-agent.exe 和 config.json 放在同一目录
echo   2. 编辑 config.json 配置服务器信息
echo   3. 双击运行 axeuh-agent.exe
echo.

pause
