@echo off
chcp 65001 >nul
title 考研数学一知识体系 - 上传到 GitHub
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0UPLOAD_TO_GITHUB.ps1"
set "EXIT_CODE=%ERRORLEVEL%"
echo.
if not "%EXIT_CODE%"=="0" (
  echo 上传未完成，请查看上方提示。
)
pause
exit /b %EXIT_CODE%
