@echo off
setlocal
set "PROJECT_ROOT=%~dp0.."
cd /d "%PROJECT_ROOT%"

if exist "%PROJECT_ROOT%\.venv\Scripts\python.exe" (
    "%PROJECT_ROOT%\.venv\Scripts\python.exe" "%~dp0launch.py" %*
) else (
    uv run python "%~dp0launch.py" %*
)

if %ERRORLEVEL% neq 0 (
    echo.
    echo GhostPush failed to start. Press any key to exit.
    pause >nul
)
endlocal
