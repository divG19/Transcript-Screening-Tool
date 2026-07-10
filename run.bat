@echo off
setlocal
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
set "HERE=%~dp0"
cd /d "%HERE%"
set "PATH=%HERE%tesseract;%PATH%"
set "TESSDATA_PREFIX=%HERE%tesseract\tessdata"
"%HERE%improved_search.exe"
echo.
echo ============================================================
echo  Tool exited. Press any key to close this window...
echo ============================================================
pause >nul
