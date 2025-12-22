@echo off
chcp 65001 >nul
cls
title Ollama Launcher

REM Kill previous Ollama instances
taskkill /f /im ollama.exe >nul 2>&1
timeout /t 2 /nobreak >nul

:menu
cls
echo ================================
echo       OLLAMA MODEL SELECTOR
echo ================================
echo [1] LIGHT - Phi3:3.8B (2GB)
echo [2] MEDIUM - DeepSeek R1:8B (5GB)
echo [3] HEAVY - Llama3.2:11B (8GB)
echo [4] BEAST - Qwen2.5:32B (20GB)
echo [0] LIST / EXIT
echo ================================
set /p choice="Choose (0-4): "

if "%choice%"=="1" set MODEL=phi3:3.8b & goto start
if "%choice%"=="2" set MODEL=deepseek-r1:8b & goto start
if "%choice%"=="3" set MODEL=llama3.2:11b & goto start
if "%choice%"=="4" set MODEL=qwen2.5:32b & goto start
if "%choice%"=="0" ollama list & pause & goto menu
goto menu

:start
cls
echo Starting %MODEL%...
ollama serve

timeout /t 3 /nobreak >nul
ollama list | findstr "%MODEL%" >nul 2>&1
if errorlevel 1 (
    echo Downloading %MODEL%...
    ollama pull %MODEL%
)

echo.
echo %MODEL% READY on http://localhost:11434 ^| Ctrl+C to return
echo.
pause
goto menu
