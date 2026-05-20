@echo off
chcp 65001 >nul
cls
title Ollama Server

REM Ustawiamy model na sztywno
set MODEL=deepseek-r1:8b

echo ==========================================
echo    STARTING OLLAMA WITH %MODEL%
echo ==========================================

REM
taskkill /f /im ollama.exe >nul 2>&1
timeout /t 1 /nobreak >nul

REM
echo Starting Ollama server...
start /b ollama serve >nul 2>&1

REM
timeout /t 5 /nobreak >nul

REM
ollama list | findstr "%MODEL%" >nul 2>&1
if errorlevel 1 (
    echo Model %MODEL% not found. Downloading...
    ollama pull %MODEL%
) else (
    echo Model %MODEL% is ready.
)

echo.
echo ==========================================
echo    SERVER READY: http://localhost:11434
echo ==========================================
echo.
echo Keep this window open. Press any key to restart...
pause >nul
goto :eof
